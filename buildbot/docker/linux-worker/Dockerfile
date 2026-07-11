FROM buildbot/buildbot-worker:v4.1.0

USER root

# Retry flaky Debian mirror downloads during the build environment
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/99-retries

# System dependencies for the Rust workspaces
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    pkg-config \
    libssl-dev \
    git \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install rustup and the stable toolchain as the buildbot user so the
# resulting Cargo tools are accessible to the worker runtime.
USER buildbot
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --default-toolchain stable --profile minimal
ENV PATH="/home/buildbot/.cargo/bin:${PATH}"

# Install a pinned, statically-linked Just binary.
# Avoids compiling from source inside the image build.
USER root
ARG JUST_VERSION=1.40.0
RUN curl -fsSL -o /tmp/just.tar.gz \
        "https://github.com/casey/just/releases/download/${JUST_VERSION}/just-${JUST_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    && tar -xzf /tmp/just.tar.gz -C /usr/local/bin just \
    && rm /tmp/just.tar.gz \
    && chmod +x /usr/local/bin/just
USER buildbot
