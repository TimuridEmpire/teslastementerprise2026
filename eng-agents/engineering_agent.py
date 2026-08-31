import json
import os
import sys
import ast
import uuid
import datetime
import subprocess
import time
import shutil
import importlib.util
from pathlib import Path
try:
    from crewai import Agent, Crew, Task
    from crewai.llm import LLM
    from crewai_tools import FileReadTool
except ImportError:  # pragma: no cover - light demo mode supports missing CrewAI
    Agent = Crew = Task = FileReadTool = None
    LLM = None

try:
    import git
except ImportError:  # pragma: no cover - push support is optional in light demo mode
    git = None

try:
    from agent_transport import ack, delegate, nack, receive
except ImportError:
    ack = delegate = nack = receive = None

try:
    from enterprise_router.agent_artifacts import write_agent_artifact
except ImportError:
    write_agent_artifact = None

try:
    from message_schema import Message
except ImportError:
    Message = None

# Model note: llama3.1 is stable but tool use is unreliable. llama3.2 has better tool-calling
# support — switch the model string below if you want to try it. llama3 (base) cannot use tools.
# Local LLM (Ollama) — override with OLLAMA_MODEL env var to switch models without editing code.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "ollama/deepseek-coder-v2:16b")
llm = (
    LLM(model=OLLAMA_MODEL, base_url="http://localhost:11434")
    if LLM is not None
    else None
)

# GitHub repo for generated output — set GITHUB_REPO_URL to a remote URL to enable push.
# e.g. GITHUB_REPO_URL=https://github.com/your-org/generated-output.git
# Leave unset to just commit locally with no push.
GITHUB_REPO_URL = os.environ.get("GITHUB_REPO_URL", "")
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", os.path.join(_REPO_ROOT, "eng_agent_testing"))

def init_output_repo():
    """Ensure OUTPUT_DIR exists as a git repo, cloning from GITHUB_REPO_URL if set."""
    if git is None:
        raise RuntimeError("GitPython is required for full Engineering mode.")
    output_path = Path(OUTPUT_DIR)
    if output_path.exists() and (output_path / ".git").exists():
        return git.Repo(output_path)
    if GITHUB_REPO_URL:
        return git.Repo.clone_from(GITHUB_REPO_URL, output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    return git.Repo.init(output_path)

def commit_and_push(repo, message="chore: agent-generated code"):
    """Stage all files, commit, and push to origin if a remote is configured."""
    repo.git.add(A=True)
    if repo.is_dirty(index=True, untracked_files=True):
        repo.index.commit(message)
        print(f"Committed: {message}")
    if GITHUB_REPO_URL and "origin" in [r.name for r in repo.remotes]:
        repo.remotes.origin.push()
        print(f"Pushed to {GITHUB_REPO_URL}")
    else:
        print("No remote configured — skipping push.")

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def make_response(sender, recipient, task_type, payload, context=None, status="done", error=None):
    if Message is not None:
        envelope = Message.create(
            sender=sender,
            recipient=recipient,
            task_type=task_type,
            context=context or {},
            payload=payload,
        ).to_dict()
        envelope["status"] = status
        envelope["error"] = error
        return envelope

    return {
        "id": str(uuid.uuid4()),
        "timestamp": now(),
        "sender": sender,
        "recipient": recipient,
        "task_type": task_type,
        "context": context or {},
        "payload": payload,
        "status": status,
        "error": error
    }

# ---------------------------------------------------------------------------
# Token budget system
# ---------------------------------------------------------------------------
# Each agent role has a budget of "virtual tokens" (a proxy for how much LLM
# work they're allowed to do per task). When a task is run through an agent
# we deduct an estimated cost. If that agent is out of budget:
#   1. A higher-privilege agent absorbs the work instead.
#   2. If NO agent has budget left, a token-request message is sent to the
#      HR agent and the current task raises a RecoverableError so the polling
#      loop can retry it after tokens are replenished.
#
# Budgets reset at the start of each new top-level task (each PM message).

DEFAULT_BUDGETS = {
    "lead":   5000,   # lead gets the most — plans, reviews, feedback
    "dev":    4000,   # dev does the heavy code-writing
    "tester": 2000,   # tester writes tests, usually shorter outputs
}

# Rough token cost estimates per operation type
OP_COSTS = {
    "plan":         800,
    "file_list":    200,
    "generate":     600,
    "test_gen":     500,
    "feedback":     600,
    "fix":          600,
}

class RecoverableError(Exception):
    """Raised when all agents are out of tokens. The polling loop will re-queue
    the message and wait for HR to replenish budgets."""
    pass

#TODO: Clarify internal engineering agent tokens vs the universal ceo tokens and make sure the naming makes it clear which is which.
# The engineering agent tokens are meant to be a proxy for how much work the engineering agents can do before needing to ask HR for more,
# while the CEO tokens are meant to be a proxy for how much work the CEO can do before needing to ask the board for more. '
# Right now the engineering agent tokens are just called "token budgets" but maybe they should be called "engineering agent token budgets"
#  or something to make it more clear that they are separate from the CEO tokens.
class TokenBudget:
    def __init__(self):
        self.budgets = dict(DEFAULT_BUDGETS)

    def reset(self):
        self.budgets = dict(DEFAULT_BUDGETS)

    def remaining(self, role: str) -> int:
        return self.budgets.get(role, 0)

    def deduct(self, role: str, op: str):
        cost = OP_COSTS.get(op, 300)
        self.budgets[role] = max(0, self.budgets.get(role, 0) - cost)

    def can_afford(self, role: str, op: str) -> bool:
        return self.budgets.get(role, 0) >= OP_COSTS.get(op, 300)

    def fallback_agent(self, db, original_role: str, op: str):
        """Return the name of the cheapest agent that can still afford the op,
        preferring higher-privilege roles. Returns None and fires an HR request
        if no one can afford it."""
        # Fallback priority: lead can do anything, dev can review, tester is last resort
        priority = ["lead", "dev", "tester"]
        for role in priority:
            if role != original_role and self.can_afford(role, op):
                print(f"[TokenBudget] '{original_role}' out of budget for '{op}' — falling back to '{role}'")
                return role
        # Nobody left — ask HR for more tokens
        self._request_tokens_from_hr(db)
        raise RecoverableError(
            f"All agents out of token budget for op '{op}'. Sent token request to HR."
        )

    def _request_tokens_from_hr(self, db):
        """Notify HR that engineering agents are out of token budget, via the
        Enterprise Router (``db`` is unused — kept for call-site compatibility)."""
        if delegate is None:
            print("[TokenBudget] Token request skipped: router transport unavailable.")
            return
        try:
            delegate(
                sender="Engineering",
                recipient="HR",
                task_type="TOKEN_REQUEST",
                payload={
                    "reason": "All engineering agents have exhausted their token budgets mid-task.",
                    "requested_budgets": DEFAULT_BUDGETS,
                },
            )
            print("[TokenBudget] Token request sent to HR agent.")
        except Exception as exc:
            print(f"[TokenBudget] Could not send TOKEN_REQUEST to HR via router: {exc}")


# ---------------------------------------------------------------------------

class FullSystem:
    # TODO: This class is a work in progress and not fully integrated yet.
    # The idea is to have a single object that encapsulates the entire system state and logic, including the agents, token budgets, and helper functions for contract validation and plan generation.
    # This way we can avoid using global variables and have a cleaner interface for the main execution flow.
    # Make sure to have a description of this class and its purpose in the docstring once it's more fully fleshed out.
    def __init__(self, db=None):
        if Agent is None or Crew is None or Task is None or llm is None:
            raise RuntimeError(
                "CrewAI is not installed. Install crewai and crewai_tools for full "
                "Engineering mode, or run with ENGINEERING_LIGHT_DEMO=1."
            )
        self.llm = llm
        self.db = db          # needed for HR token requests
        self.tokens = TokenBudget()

        # Helper: resolve which CrewAI Agent object to use for a role, respecting budget
        self._agents_by_role = {}  # populated after agents are defined below

        def _agent_for(role, op):
            if os.environ.get("DISABLE_TOKEN_BUDGET"):
                return self._agents_by_role[role]
            if self.tokens.can_afford(role, op):
                self.tokens.deduct(role, op)
                return self._agents_by_role[role]
            fallback_role = self.tokens.fallback_agent(self.db, role, op)
            self.tokens.deduct(fallback_role, op)
            return self._agents_by_role[fallback_role]

        self._agent_for = _agent_for
        
        #IDK how much of an issue this will be in the long run but the agent's memories are causing them to sometimes mess up their outputs.
        # setting memory to false is supposed to fix this but doesn't really work, i've been using "reset_memories(command_type="all")" after tasks which seems to have maybe helped?
        # Lead Developer (Planner + Reviewer)
        self.lead = Agent(
            role="Lead Developer",
            goal="Plan tasks, review outputs, and ensure code quality.",
            backstory="""You are a part of the engineering team of a company consisting of AI agents. You are a senior engineer with years of experience and strong leadership skills.
                        You are the leader of the team and your job is to create clear, actionable development plans based on product specifications, review the code written by your 
                        team, and give specific feedback to ensure the final code is clean, efficient, well-structured, and meets the specifications.
            """,
            memory=False,
            cache=False,
            llm=self.llm
        )

        # Software Developer
        self.dev = Agent(
            role="Software Developer",
            goal="Write clean, functional code.",
            backstory="""You are a part of the engineering team of a company consisting of AI agents. You are an experienced developer with a strong focus on writing clean, maintainable code.
                        Your job is to write code based on the development plans created by your lead developer and to fix any issues in the code based on the feedback you receive from your lead.
                        The code you write should be efficient, well-structured, and meet the specifications provided to you.""",
            memory=False,
            llm=self.llm
        )

        # Testing Agent
        self.tester = Agent(
            role="Testing Engineer",
            goal="Write and evaluate unit tests for code you are provided with.",
            backstory="""You are a part of the engineering team of a company consisting of AI agents. You are responsible for writing unit tests 
                        for the code written by your development agent and evaluating whether the code meets the specifications based on the results of these tests.
            """,
            memory=False,
            llm=self.llm
        )

        # Register agents so _agent_for can look them up by role name
        self._agents_by_role = {
            "lead":   self.lead,
            "dev":    self.dev,
            "tester": self.tester,
        }

    def _required_contract(self, spec):
        """Return required interface checks inferred from the task spec.
        This prevents generated code from passing weak tests while missing
        critical API methods.
        """
        return {}

    def _is_streamlit_spec(self, spec):
        return "streamlit" in spec.lower()

    def _clean_output_dir(self):
        output_path = Path(OUTPUT_DIR)
        output_path.mkdir(parents=True, exist_ok=True)
        for child in output_path.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def _contract_hint(self, spec, file):
        """Prompt hint injected into generation prompts for files that have
        strict API requirements."""
        contracts = self._required_contract(spec)
        entry = contracts.get(file)
        if not entry:
            return ""
        method_lines = "\n".join(f"- {m}(...)" for m in entry["methods"])
        return f"""
                REQUIRED API CONTRACT FOR THIS FILE:
                - Define class `{entry['class']}`.
                - The constructor MUST accept a `max_attempts` argument, preferably with a default.
                - The class MUST include these public methods:
                {method_lines}
                - Do not rename these methods.
        """

    def validate_contract(self, spec, source_files):
        """Validate required class/method contract in generated source files.
        Returns (ok, message)."""
        contracts = self._required_contract(spec)
        if not contracts:
            return True, "No explicit contract checks required for this spec."

        for file_name, contract in contracts.items():
            if file_name not in source_files:
                return False, f"Missing required source file: {file_name}"

            file_path = Path(OUTPUT_DIR) / file_name
            if not file_path.exists():
                return False, f"Required file not generated: {file_name}"

            try:
                tree = ast.parse(file_path.read_text(encoding="utf-8"))
            except Exception as e:
                return False, f"Contract check parse error in {file_name}: {e}"

            class_node = None
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == contract["class"]:
                    class_node = node
                    break

            if class_node is None:
                return False, f"Missing required class {contract['class']} in {file_name}"

            method_nodes = {
                node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)
            }
            method_names = set(method_nodes)
            for method in contract["methods"]:
                if method not in method_names:
                    return False, f"Missing required method {contract['class']}.{method} in {file_name}"

        return True, "Contract checks passed."

    #Creates a plan based off which the rest of the code is written
    #The plan is consistently pretty good and is currently being stored in plan.md
    #The plan tends to have a lot of formatting either avoid storing it as a string/text file or copy over some of the 'STRICT RULES' form the 
    #coding prompts to reduce the fancy formatting
    def create_plan(self, spec):

        chosen_lead = self._agent_for("lead", "plan")
        streamlit_hint = ""
        if self._is_streamlit_spec(spec):
            streamlit_hint = """
                STREAMLIT APP REQUIREMENTS:
                - The app must use Streamlit for the UI. Do NOT use input() or print() for interaction.
                - Game logic should go in a separate module (e.g. game.py) so it can be unit tested independently.
                - A main.py file must be created that launches the Streamlit app (e.g. contains `import streamlit as st` and the UI code).
                - A tests.py file must test the game logic module (not the Streamlit UI).
                - The player must be able to launch the app by running: streamlit run main.py
            """
        task = Task(
            description=f"""
                You are the Lead developer of an engineering team consisting of AI coding agents. Your job is to create a clear, actionable development plan based on the given specification.
                The plan will consist of a numbered list of steps that the development agent can follow to implement the required functionality. Be sure to break down the tasks into manageable pieces and consider any edge cases or potential challenges.
                Your next task will be to determine what files need to be created for the project, so mention potential files that might into which code will need to be organized in your plan.

                IMPORTANT:
                - A git repository has already been created for this project, so you do not need to include any steps related to setting up a repository or version control in your plan.
                - no folder structure is necessary, just a list of files with extensions that are necessary for the project based on the specifications and the plan you have created.
                - Focus ONLY on the development steps necessary to implement the functionality based on the specifications, and organizing the code into appropriate files.
                {streamlit_hint}

                Spec:
                {spec}
            """,
            expected_output="A clear, organized, numbered list of development steps that will allow your team to achieve the specified functionality.",
            agent=chosen_lead
        )
        crew = Crew(agents=[chosen_lead], tasks=[task])
        plan = str(crew.kickoff())
        crew.reset_memories(command_type="all")
        return str(plan)  # Return the output of the first task, which is the development plan

    #function to figure out what files need to be created for the project based off the spec and the plan made by the lead in create_plan
    #none of these files are actually created until the code is generated in generate_code, this function just determines what files need to be created and returns a list of the file names with extensions
    #IMPORTANT: the testing file is always named "tests" and is the last one in the outputted list. This is used throughout the rest of the code
    def create_necessary_files(self, spec, plan):


        chosen_lead = self._agent_for("lead", "file_list")
        streamlit_file_hint = ""
        if self._is_streamlit_spec(spec):
            streamlit_file_hint = """
                STREAMLIT REQUIREMENT: You MUST include main.py (the Streamlit UI entry point) as a source file.
                The file list must end with tests.py. Example output: game.py,main.py,tests.py"""
        task_create_files = Task(
            description=f"""
                You are the lead developer of an engineering team consisting of AI coding agents. You are woking on building a project following the specifications provided. Based on the development plan you have created, determine what files need to be created for this project.
                To complete this task, create a list containing the names of the files that need to be created along with the extension (e.g. "app.py" for the main code, "test_app.py" for tests, etc.). The files you list should be seperated by commas with no spaces or any other additional formatting in between.
                You will only be making one testing file! Name it "tests" and have it be the last one in the list!
                {streamlit_file_hint}
                
                IMPORTANT:
                - no folder structure is necessary, just a list of files with extensions that are necessary for the project based on the specifications and the plan you have created.
                - There will only be one testing file, and it should be named "tests" with the appropriate extension based on the type of code you are writing (e.g. "tests.py" for Python).
                - This testing file should be the last one in the list of files you output.

                STRICT RULES:
                - Output ONLY the file names with extensions in a list format, separated by commas with no spaces or any other additional formatting in between.
                - NO invalid extensions or file names that do not follow standard conventions for the type of code they will contain.
                - NO markdown (no ``` )
                - NO explanations
                - NO comments
                - NO new folders or directories, just files to add to the root directory of the project
                - All the output from the first character to the last must be valid file names with extensions that are necessary for the project based on the specifications.

                The plan you have created:
                {plan}

                Spec:
                {spec}
            """,
            expected_output="A list of necessary files that need to be created for the project, including their names and extensions, seperated by commas with no spaces or any other additional formatting in between.",
            agent=chosen_lead
        )
        crew_files = Crew(agents=[chosen_lead], tasks=[task_create_files])
        files = [name.strip() for name in str(crew_files.kickoff()).split(",") if name.strip()]
        crew_files.reset_memories(command_type="all")

        # Enforce mandatory source files so contract checks remain satisfiable.
        required_sources = []
        # For Streamlit apps, always include main.py as a source file.
        if self._is_streamlit_spec(spec) and "main.py" not in required_sources:
            required_sources.append("main.py")
        if files:
            testing_file = files[-1]
            source_files = files[:-1]
            for req in required_sources:
                if req not in source_files:
                    source_files.append(req)
            files = source_files + [testing_file]
        else:
            # Defensive fallback: create at least one source + one test file.
            files = required_sources + ["tests.py"]

        return files

    def clean_code(self, code):
        """Basic code cleaning to reduce formatting issues. This can be expanded as needed."""
        # Remove markdown code fences if present
        if "```Python" in code or "```python" in code:
            code = code.replace("```Python", "").replace("```python", "")
        if "```" in code:
            code = code.replace("```", "")
        return code.strip()

    #function to generate code based on the spec and the plan created by the lead, organized into the files determined by create_necessary_files
    #the code is generated one file at a time, and after each file is generated it is written to a file (the file is created as it is written to)
    def generate_code(self, spec, plan, file, file_list=None):

        chosen_dev = self._agent_for("dev", "generate")
        streamlit_hint = ""
        if self._is_streamlit_spec(spec) and file == "main.py":
            streamlit_hint = """
                STREAMLIT SPECIFIC RULES for main.py:
                - This file IS the Streamlit app entry point.
                - Import streamlit as st and use st.* components for all UI (buttons, text input, st.write, etc.).
                - Do NOT use input() or print() for user interaction.
                - Import game logic from the other source file(s) in the project.
                - The player launches this app with: streamlit run main.py
            """
        task = Task(
            description=f"""
                You are a software developer on an engineering team consisting of AI coding agents. Your task is to look at the development plan created by your lead developer
                and write the code from that plan that would need to go into the file "{file}" to implement the functionality specified in the specifications. Write clean, efficient, 
                well-structured code that meets the specifications and follows best practices for the type of code you are writing.
                Alongside this file, your teammates will create code for the other necessary files. The list of these files is as follows: {file_list}. The code you write should be organized in a way that makes sense based on the purpose of the file and the overall structure of the project.

                STRICT RULES:
                - Output ONLY raw code
                - NO syntax errors in the code you output
                - NO markdown (no ``` )
                - NO explanations
                - NO comments unless necessary
                - The first character must be valid executable code
                                - NO interactive input calls (no input(...)).
                                - NO top-level executable statements besides imports, class/function
                                    definitions, and optional guarded main block:
                                    if __name__ == '__main__': ...
                - ONLY write code that would go in the file "{file}", do not write code that would go in any of the other files in the project.
                {streamlit_hint}

                Spec:
                {spec}

                Plan:
                {plan}

                {self._contract_hint(spec, file)}

                Return ONLY valid code.
            """,
            expected_output="Just code that meets the specification.",
            agent=chosen_dev
        )
        crew = Crew(agents=[chosen_dev], tasks=[task])
        result = self.clean_code(str(crew.kickoff()))
        crew.reset_memories(command_type="all")
        # Write generated file into OUTPUT_DIR so it stays separate from the agent's own code
        out_path = Path(OUTPUT_DIR) / file
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(str(result))

        return result

    def generate_tests(self, spec, plan, file, source_files, feedback=""):
        """Dedicated test-generation prompt — produces more reliable test code than the
        generic generate_code prompt because it explicitly tells the agent what the source
        files are and what they need to test."""

        chosen_tester = self._agent_for("tester", "test_gen")
        source_listing = "\n".join(source_files)
        streamlit_test_hint = ""
        if self._is_streamlit_spec(spec):
            # Exclude main.py from what gets tested — Streamlit UI is not unit-testable.
            testable_sources = [f for f in source_files if f != "main.py"]
            source_listing = "\n".join(testable_sources)
            streamlit_test_hint = """
                STREAMLIT NOTE: Do NOT import streamlit or test the Streamlit UI.
                Only test the game logic from the non-UI source files.
                Do not import main.py in the tests.
            """
        task = Task(
            description=f"""
                You are a Testing Engineer on a team of AI coding agents. Write a complete unit test file
                named "{file}" that tests all the functionality described in the spec and plan below.
                The source files being tested are: {source_listing}

                STRICT RULES:
                - Output ONLY raw code
                - NO syntax errors in the code you output
                - NO markdown (no ``` )
                - NO explanations
                - NO comments unless necessary
                - The first character must be valid executable code
                - Use unittest. Do NOT rely on interactive input or network access.
                - Every test must be deterministic (seed random if needed).
                - Always end the file with: if __name__ == '__main__': unittest.main()
                - Tests MUST NOT require user input().
                - Tests must import source modules without triggering gameplay.
                {streamlit_test_hint}

                Spec:
                {spec}

                Plan:
                {plan}

                Prior feedback from lead (if any):
                {feedback}

                                REQUIRED TEST COVERAGE:
                                - Include at least one test that instantiates required classes and
                                    asserts each required public method exists.
                                - Include at least one behavioral test for each required method.

                Return ONLY valid test code.
            """,
            expected_output="Only valid, runnable unit test code.",
            agent=chosen_tester
        )
        crew = Crew(agents=[chosen_tester], tasks=[task])
        result = self.clean_code(str(crew.kickoff()))
        crew.reset_memories(command_type="all")
        out_path = Path(OUTPUT_DIR) / file
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result)
        return result


    def run_tests(self, testing_file):
        """Run a test file and return (passed: bool, detail: str).
        Supports Python (.py) and JavaScript (.js via node) test files.
        Produces detailed error output so the lead agent knows exactly what failed.
        """
        test_path = Path(testing_file)
        ext = test_path.suffix.lower()

        # Run from the test file's own directory so relative imports in generated
        # code work consistently, and avoid duplicating OUTPUT_DIR in the path.
        run_cwd = str(test_path.parent) if test_path.parent != Path("") else None
        run_target = test_path.name if run_cwd else str(test_path)

        if ext == ".py":
            runner = [sys.executable, run_target]
        elif ext == ".js":
            runner = ["node", run_target]
        else:
            return False, f"Unsupported test file type: {ext}. Only .py and .js are supported."

        try:
            result = subprocess.run(
                runner,
                capture_output=True,
                text=True,
                timeout=30,  # raised from 5s — some tests need more time to start up
                cwd=run_cwd
            )
            combined = result.stdout + ("\nSTDERR:\n" + result.stderr if result.stderr.strip() else "")
            print(combined)

            if result.returncode == 0:
                return True, "All tests passed successfully."
            else:
                # Give the lead agent both stdout and stderr for diagnosis.
                detail = (
                    f"Tests failed (exit code {result.returncode}).\n"
                    f"--- test output ---\n{result.stdout}\n"
                    + (f"--- stderr ---\n{result.stderr}" if result.stderr.strip() else "")
                )
                return False, detail
        except subprocess.TimeoutExpired:
            return False, "Test execution timed out after 30 seconds. Check for infinite loops or blocking input."
        except FileNotFoundError as e:
            return False, f"Test runner not found: {e}. Make sure python/pytest or node is installed and on PATH."
        except Exception as e:
            return False, str(e)

    # Main loop: create plan -> generate initial code -> run tests -> lead feedback -> fix -> repeat
    def review_and_iterate(self, spec, max_iterations=10):
        self.tokens.reset()  # fresh budget for each new top-level task
        repo = init_output_repo()
        self._clean_output_dir()

        plan = self.create_plan(spec)
        with open(Path(OUTPUT_DIR) / "plan.md", "w", encoding="utf-8") as f:
            f.write(plan)
        files = self.create_necessary_files(spec, plan)
        testing_file = files[-1]  # testing file is always last
        source_files = files[:-1]
        print(f"Files to create: {files}")

        iteration = 0

        # Generate source files with the standard code prompt
        for file in source_files:
            self.generate_code(spec, plan, file, file_list=files)
        # Generate the test file with the dedicated test prompt for better reliability
        self.generate_tests(spec, plan, testing_file, source_files)

        # Enforce API contract before running tests so weak tests cannot mask
        # missing required methods.
        contract_ok, contract_message = self.validate_contract(spec, source_files)
        if not contract_ok:
            success_status, error_message = False, contract_message
        else:
            success_status, error_message = self.run_tests(str(Path(OUTPUT_DIR) / testing_file))
        if success_status:
            commit_and_push(repo, f"feat: initial generated code ({testing_file} passing)")
            return {"status": "success", "iterations": iteration}

        # Feedback + fix loop
        while iteration < max_iterations:
            iteration += 1

            # Step 1: Lead looks at the test errors and explains what's likely wrong
            chosen_lead = self._agent_for("lead", "feedback")
            find_problems_task = Task(
                description=f"""
                    Your team has finished writing code based on the specifications and the development plan you created, but the code is not passing all the tests it needs to.
                    Your job is to look over the errors that are occuring in the tests and explain potential reasons why these errors might be occuring based on the specifications and the development plan you created.
                    Be as specific as possible in your feedback so that your team can use it to fix the code and ensure it meets the specifications.

                    The errors that are occuring in the tests are as follows:
                    {error_message}

                    The original plan you created for the development of this project is as follows:
                    {plan}

                    The specifications for this project are as follows:
                    {spec}
                """,
                expected_output="Specific feedback that your team can use to fix the code.",
                agent=chosen_lead
            )
            crew = Crew(agents=[chosen_lead], tasks=[find_problems_task])
            feedback = str(crew.kickoff())
            crew.reset_memories(command_type="all")
            print(f"Iteration {iteration} — Lead feedback:\n{feedback}")

            # Step 2: Dev re-generates each non-test file using the feedback
            for file in files[:-1]:
                chosen_dev = self._agent_for("dev", "fix")
                fix_task = Task(
                    description=f"""
                        Your lead developer has reviewed the code and provided feedback on why it is failing tests.
                        Rewrite the code for the file "{file}" from scratch, incorporating the feedback to fix the issues.

                        STRICT RULES:
                        - Output ONLY raw code
                        - NO markdown (no ``` )
                        - NO explanations
                        - NO comments unless necessary
                        - The first character must be valid executable code

                        Lead feedback:
                        {feedback}

                        Original spec:
                        {spec}

                        Development plan:
                        {plan}
                    """,
                    expected_output="Only valid executable code for the file.",
                    agent=chosen_dev
                )
                fix_crew = Crew(agents=[chosen_dev], tasks=[fix_task])
                fixed_code = str(fix_crew.kickoff())
                fix_crew.reset_memories(command_type="all")
                out_path = Path(OUTPUT_DIR) / file
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(fixed_code)

            # Step 3: Always regenerate the test file too, so syntax or assertion
            # issues in tests can be corrected during iterations.
            self.generate_tests(spec, plan, testing_file, source_files, feedback)

            contract_ok, contract_message = self.validate_contract(spec, source_files)
            if not contract_ok:
                success_status, error_message = False, contract_message
            else:
                success_status, error_message = self.run_tests(str(Path(OUTPUT_DIR) / testing_file))
            if success_status:
                commit_and_push(repo, f"fix: iteration {iteration} — tests now passing")
                return {"status": "success", "iterations": iteration}

        return {"status": "failed", "iterations": iteration}


class EngineeringAgent:
    def __init__(self, db=None):
        self.name = "Engineering"
        self.db = db

    def _build_spec(self, task_type, payload):
        if task_type == "generate_code":
            return payload["spec"]

        if task_type == "IMPLEMENT_FEATURE":
            criteria = "\n".join(f"- {c}" for c in payload.get("acceptance_criteria", []))
            return (
                f"Feature: {payload.get('feature_name', 'Unnamed feature')}\n"
                f"Feature ID: {payload.get('feature_id', '')}\n"
                f"Description: {payload.get('spec') or payload.get('description', '')}\n"
                f"Acceptance criteria:\n{criteria}"
            )

        raise ValueError(f"Unknown task_type: {task_type}")

    def _generated_files(self):
        output_path = Path(OUTPUT_DIR)
        if not output_path.exists():
            return []
        return sorted(
            str(path.relative_to(output_path)).replace("\\", "/")
            for path in output_path.rglob("*")
            if path.is_file() and ".git" not in path.parts
        )

    def _artifact_body(self, spec, result=None, error=None):
        generated_files = self._generated_files()
        files_section = "\n".join(f"- `{file}`" for file in generated_files) or "- No files generated."
        test_status = "not run"
        if result:
            test_status = "passed" if result.get("status") == "success" else "failed"
        review_notes = (
            f"Review and iteration completed in {result.get('iterations', 0)} iteration(s)."
            if result else "Processing stopped before review iteration completed."
        )
        error_section = f"\n\n## Error\n\n{error}" if error else ""

        return (
            "## Engineering Request\n\n"
            f"{spec}\n\n"
            "## Generated Files\n\n"
            f"{files_section}\n\n"
            "## Test Status\n\n"
            f"{test_status}\n\n"
            "## Review Notes\n\n"
            f"{review_notes}"
            f"{error_section}\n"
        )

    def _write_artifact(self, message, spec, result=None, error=None):
        if write_agent_artifact is None:
            if self.db is None:
                raise RuntimeError(
                    "Router artifact writer is unavailable. Ensure enterprise_router is on PYTHONPATH."
                )
            return None

        artifact = write_agent_artifact(
            self.name,
            title="Engineering Feature Implementation",
            artifact_type="engineering",
            body=self._artifact_body(spec, result=result, error=error),
            metadata={
                "run_id": message.get("context", {}).get("run_id"),
                "project_id": message.get("context", {}).get("project_id"),
                "status": "error" if error else result.get("status", "unknown"),
                "generated_files": self._generated_files(),
            },
            source_message_id=str(message.get("id", "")),
            source_task_type=str(message.get("task_type", "")),
        )
        return artifact.get("artifact_id") if isinstance(artifact, dict) else None

    def _light_result(self, spec):
        return {
            "status": "light_demo",
            "iterations": 0,
            "summary": "Engineering light demo produced a review artifact without generating code.",
            "generated_code": False,
            "spec_preview": spec[:500],
        }

    def _response_context(self, message):
        context = dict(message.get("context") or {})
        context["source_message_id"] = str(message.get("id", ""))
        context["source_task_type"] = str(message.get("task_type", ""))
        return context

    def handle_message(self, message):
        task_type = message["task_type"]
        payload = message.get("payload", {})
        requester = message.get("sender", "PM")
        context = self._response_context(message)

        try:
            spec = self._build_spec(task_type, payload)
            use_light_demo = (
                os.environ.get("ENGINEERING_LIGHT_DEMO", "").strip().lower()
                in {"1", "true", "yes", "on"}
                or Agent is None
                or Crew is None
                or Task is None
            )
            if use_light_demo:
                result = self._light_result(spec)
            else:
                system = FullSystem(db=self.db)
                max_iterations = int(os.environ.get("MAX_ITERATIONS", "10"))
                result = system.review_and_iterate(spec, max_iterations)
            artifact_id = self._write_artifact(message, spec, result=result)
            is_success = result.get("status") in {"success", "light_demo"}
            response_payload = {
                "status": "done" if is_success else "error",
                "summary": (
                    "Feature implementation completed."
                    if result.get("status") == "success"
                    else "Engineering light demo artifact produced; no code was generated."
                    if result.get("status") == "light_demo"
                    else "Feature implementation did not pass engineering validation."
                ),
                "artifact_id": artifact_id,
                "details": result,
                "generated_files": self._generated_files(),
                "next_actions": [
                    "Requester reviews the engineering artifact.",
                    "Run the generated project from the configured OUTPUT_DIR.",
                ],
            }
            return make_response(
                sender=self.name,
                recipient=requester,
                task_type="FEATURE_RESPONSE",
                context=context,
                payload=response_payload,
                status=response_payload["status"]
            )

        except Exception as e:
            spec = ""
            try:
                spec = self._build_spec(task_type, payload)
            except Exception:
                pass
            artifact_id = self._write_artifact(message, spec, error=str(e)) if spec else None
            return make_response(
                sender=self.name,
                recipient=requester,
                task_type="FEATURE_RESPONSE",
                context=context,
                payload={
                    "status": "error",
                    "summary": "Engineering could not complete the requested task.",
                    "artifact_id": artifact_id,
                    "error": str(e),
                    "recoverable": False,
                },
                status="error",
                error=str(e)
            )

    def submit_response(self, response, source_message):
        if delegate is None:
            raise RuntimeError(
                "Router transport is unavailable. Ensure agent_transport.py is on PYTHONPATH."
            )

        delegate(
            sender=response["sender"],
            recipient=response["recipient"],
            task_type=response["task_type"],
            context=response.get("context", {}),
            payload=response.get("payload", {}),
            routing_hints={
                "urgency": "normal",
                "provenance_source": "engineering_agent",
                "provenance_agent": self.name,
                "dedupe_key": (
                    f"{response.get('context', {}).get('run_id', 'no-run')}:"
                    f"{source_message.get('id')}:engineering-feature-response"
                ),
            },
        )


def process_one_router_message(agent):
    if receive is None or ack is None or nack is None:
        raise RuntimeError(
            "Router transport is unavailable. Ensure agent_transport.py is on PYTHONPATH."
        )

    message = receive("Engineering")
    if message is None:
        return False

    message_id = str(message["id"])
    print(f"\nPicked up router message: {message_id} ({message['task_type']})")

    try:
        response = agent.handle_message(message)
        agent.submit_response(response, message)
    except Exception as exc:
        nack(message_id, "Engineering", reason=str(exc))
        print(f"Message {message_id} nacked. Error: {exc}")
        return True

    ack(message_id, "Engineering")
    print(f"Feature response submitted and source message acked: {message_id}")
    print(json.dumps(response, indent=2))
    return True

def run_router_worker():
    agent = EngineeringAgent(db=None)
    poll_interval = int(os.environ.get("POLL_INTERVAL_SECONDS", "10"))

    print(f"Engineering agent started. Polling Enterprise Router every {poll_interval}s...")

    while True:
        if not process_one_router_message(agent):
            time.sleep(poll_interval)

if __name__ == "__main__":
    run_router_worker()
