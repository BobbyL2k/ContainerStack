# Platform: linux/amd64 only
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG GO_VERSION=1.26.5

ENV GO_VERSION=${GO_VERSION}
ENV GOROOT=${HOME}/go-bin
ENV GOPATH=${HOME}/go
ENV PATH=${GOROOT}/bin:${GOPATH}/bin:${PATH}

RUN mkdir -p "${HOME}/go-bin" && \
    curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" | \
    tar -C "${HOME}/go-bin" --strip-components=1 -xzf - && \
    go version
