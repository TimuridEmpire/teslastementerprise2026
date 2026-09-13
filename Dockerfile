# Shared image for the router and every department-agent worker.
#
# Pinned to 3.13 deliberately: crewai (see requirements.txt) requires
# Python <3.14, which is why local development on this machine needed a
# second venv just for the Engineering worker. A container isn't tied to
# the host's system Python, so there's no reason to split runtimes here --
# one image, one interpreter, for the router and every worker alike.
# Only the router service actually uses this -- build_runner.py shells out
# to `docker` to sandbox a build's generated code (see that module's
# docstring). Copying just the static CLI binary (no daemon) from the
# official docker image is the standard lightweight way to get `docker`
# into a container that talks to the *host's* daemon via a mounted socket
# (docker-compose.yml mounts /var/run/docker.sock into the router
# service) -- this is Docker-outside-of-Docker, not Docker-in-Docker.
FROM docker:27-cli AS docker-cli

FROM python:3.13-slim

WORKDIR /app

# git: needed by eng-agents/engineering_agent.py's GitPython-based commit of
# generated code (init_output_repo/commit_and_push). curl: used by the
# router service's own container healthcheck in docker-compose.yml.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# No ENTRYPOINT/CMD -- docker-compose.yml sets one `command:` per service
# (the router, or `run_single_agent.py <Name>` for each worker), since this
# one image serves all of them.
