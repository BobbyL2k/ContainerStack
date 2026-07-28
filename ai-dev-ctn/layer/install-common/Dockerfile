# syntax=docker/dockerfile:1

ARG BASE_IMAGE=debian:bookworm-slim

FROM ${BASE_IMAGE} AS git-builder

ARG GIT_VERSION=2.54.0
ARG GIT_SHA256=f689162364c10de79ef89aa8dbf48731eb057e34edbbd20aca510ce0154681a3

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        gettext \
        libcurl4-openssl-dev \
        libexpat1-dev \
        libssl-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN curl --fail --show-error --location \
        --output "git-${GIT_VERSION}.tar.xz" \
        "https://www.kernel.org/pub/software/scm/git/git-${GIT_VERSION}.tar.xz" \
    && echo "${GIT_SHA256}  git-${GIT_VERSION}.tar.xz" | sha256sum --check - \
    && tar -xf "git-${GIT_VERSION}.tar.xz"

WORKDIR /src/git-${GIT_VERSION}

RUN make -j"$(nproc)" \
        prefix=/usr/local \
        NO_TCLTK=YesPlease \
        all \
    && make \
        prefix=/usr/local \
        NO_TCLTK=YesPlease \
        DESTDIR=/git-install \
        install


FROM ${BASE_IMAGE}

# Installing the distro Git package is intentional here:
# it reliably supplies Git's runtime libraries and helper dependencies.
# /usr/local/bin/git from the source build takes precedence over /usr/bin/git.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        openssh-client \
        curl \
        libatomic1 \
        wget \
        unzip \
        util-linux \
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
        bubblewrap \
        pkg-config \
        ffmpeg \
        fd-find \
        ripgrep \
        libasound2t64 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcairo2 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libglib2.0-0 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libpango-1.0-0 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxkbcommon0 \
        libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=git-builder /git-install/usr/local/ /usr/local/
