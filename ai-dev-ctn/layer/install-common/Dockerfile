ARG BASE_IMAGE
FROM ${BASE_IMAGE}

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libatomic1 \
    git \
    wget \
    unzip \
    jq \
    make \
    tree \
    less \
    nano \
    file \
    diffutils \
    procps \
    iputils-ping \
    dnsutils \
    netcat-openbsd \
    lsof \
    strace \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*
