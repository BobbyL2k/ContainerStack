ARG BASE_IMAGE=dev_base:latest
FROM ${BASE_IMAGE}

ARG UV_VERSION=0.11.16

RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh

# NOTE adding /home/ubuntu/.local/bin to PATH is not required
#      this is assumed to already be done by the base image.
# ENV PATH="/home/ubuntu/.local/bin:$PATH"
