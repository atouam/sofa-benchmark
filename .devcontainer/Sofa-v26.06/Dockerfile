FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /uvx /usr/local/bin/

ARG SOFA_ZIP_URL="https://github.com/sofa-framework/sofa/releases/download/v26.06.00/SOFA_v26.06.00_Linux_Python3.12.zip"

ENV DEBIAN_FRONTEND=noninteractive \
    SOFA_ROOT=/opt/sofa \
    VIRTUAL_ENV=/home/vscode/sofa-venv

ENV UV_PROJECT_ENVIRONMENT=${VIRTUAL_ENV} \
    PATH=${VIRTUAL_ENV}/bin:${SOFA_ROOT}/bin:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        unzip \
        libgl1 \
        libgtk-3-0t64 \
        libopengl0 \
        python3.12-dev \
        python3.12-venv \
        libglu1-mesa \
        libxft2 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/sofa \
    && curl -fsSL "$SOFA_ZIP_URL" -o /tmp/sofa.zip \
    && unzip -q /tmp/sofa.zip -d /tmp/sofa \
    && mv /tmp/sofa/* "$SOFA_ROOT" \
    && rm -rf /tmp/sofa /tmp/sofa.zip \
    && printf '%s\n' 'SofaPython3 NO_VERSION' >> "$SOFA_ROOT/lib/plugin_list.conf"

USER vscode

RUN uv venv "$VIRTUAL_ENV" --python /usr/bin/python3.12 \
    && uv pip install \
        --python "$VIRTUAL_ENV/bin/python" \
        numpy \
        scipy \
        pybind11==2.12.0

RUN site_packages="$("$VIRTUAL_ENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')" \
    && for plugin in SofaPython3 STLIB SofaImGui SoftRobots; do \
        plugin_packages="$SOFA_ROOT/plugins/$plugin/lib/python3/site-packages"; \
        if test -d "$plugin_packages"; then \
            printf '%s\n' "$plugin_packages"; \
        fi; \
    done > "$site_packages/sofa-plugins.pth" \
    && "$VIRTUAL_ENV/bin/python" -c \
        'import Sofa; import Sofa.Core; import Sofa.Simulation'

WORKDIR /home/vscode/sofagen