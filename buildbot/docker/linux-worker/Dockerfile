FROM buildbot/buildbot-worker:v4.0.0

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

# Install Just
RUN cargo install just
