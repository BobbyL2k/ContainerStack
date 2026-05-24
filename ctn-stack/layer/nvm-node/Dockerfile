ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG NODE_VERSION=26.2.0

ENV HOME=/home/ubuntu
ENV NVM_DIR=/home/ubuntu/.nvm
ENV PATH=${NVM_DIR}/versions/node/v${NODE_VERSION}/bin:${PATH}

SHELL ["/bin/bash", "-lc"]

RUN . "${NVM_DIR}/nvm.sh" && \
    nvm install "${NODE_VERSION}" && \
    nvm alias default "${NODE_VERSION}"
