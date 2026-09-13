# Shared image for the router and every department-agent worker.
#
# Pinned to 3.13 deliberately: crewai (see requirements.txt) requires
# Python <3.14, which is why local development on this machine needed a
# second venv just for the Engineering worker. A container isn't tied to
# the host's system Python, so there's no reason to split runtimes here --
# one image, one interpreter, for the router and every worker alike.
FROM python:3.13-slim

WORKDIR /app

# git: needed by eng-agents/engineering_agent.py's GitPython-based commit of
# generated code (init_output_repo/commit_and_push). curl: used by the
# router service's own container healthcheck in docker-compose.yml.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# No ENTRYPOINT/CMD -- docker-compose.yml sets one `command:` per service
# (the router, or `run_single_agent.py <Name>` for each worker), since this
# one image serves all of them.
