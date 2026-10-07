FROM mcr.microsoft.com/devcontainers/base:ubuntu-20.04
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ARG SOFA_ZIP_URL

ENV DEBIAN_FRONTEND=noninteractive \
    SOFA_ROOT=/opt/sofa \
    VIRTUAL_ENV=/opt/venvs/sofa \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_CACHE_DIR=/opt/uv/cache \
    PATH=/opt/venvs/sofa/bin:/opt/sofa/bin:${PATH} 

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libegl1 \
        libgtk-3-0 \
        libopengl0 \
        libpython3.8-dev \
        libasound2 \
        liboce-modeling11 \
        libnss3 \
        libxtst6 \
    && rm -rf /var/lib/apt/lists/*
    
RUN curl -fsSL "$SOFA_ZIP_URL" -o /tmp/sofa.zip \
    && unzip -q /tmp/sofa.zip -d /opt \
    && ln -s "$(find /opt -maxdepth 1 -type d -name 'SOFA*' | head -n 1)" "$SOFA_ROOT" \
    && echo "SofaPython3 1.0" >> "$SOFA_ROOT/lib/plugin_list.conf" \
    && chown -R vscode:vscode "$SOFA_ROOT" "$(readlink -f "$SOFA_ROOT")" \
    && rm -f /tmp/sofa.zip


RUN uv python install 3.8 \
    && uv venv "$VIRTUAL_ENV" --python 3.8 --seed

RUN python -m pip install --no-cache-dir \
        pip==23.3.2 \
        setuptools==65.5.0 \
        wheel==0.38.4

RUN python -m pip install --no-cache-dir \
        gym==0.21.0 \
        numpy \
        scipy \
        stable-baselines3[extra]==1.7.0 \
        rlberry==0.5.0 \
        psutil \
        pygame \
        glfw \
        pyopengl \
        imageio \
        imageio-ffmpeg \
        colorama \
        tensorboard

WORKDIR /workspaces

RUN git clone https://github.com/SofaDefrost/SofaGym.git /workspaces/SofaGym \
    && python -m pip install --no-cache-dir -v -e /workspaces/SofaGym \
    && chown -R vscode:vscode /opt/uv /opt/venvs /workspaces/SofaGym

ENV PYTHONPATH=/opt/sofa/plugins/SofaPython3/lib/python3/site-packages:\
/opt/sofa/plugins/STLIB/lib/python3/site-packages:\
/opt/sofa/plugins/SofaImGui/lib/python3/site-packages