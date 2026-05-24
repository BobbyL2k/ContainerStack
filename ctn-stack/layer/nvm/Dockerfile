ARG BASE_IMAGE=dev_base:latest
FROM ${BASE_IMAGE}

ARG NVM_VERSION=0.40.4

ENV HOME=/home/ubuntu
ENV NVM_DIR=/home/ubuntu/.nvm

RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v${NVM_VERSION}/install.sh | bash
