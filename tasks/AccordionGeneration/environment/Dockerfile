# Build from the official SOFA release; no locally built base image is required.
FROM ubuntu:24.04
ARG SOFA_ZIP_URL=https://github.com/sofa-framework/sofa/releases/download/v26.06.00/SOFA_v26.06.00_Linux_Python3.12.zip
ARG SOFA_ZIP_SHA256=2a5c80dd012a433c36bae11ed06df701eb447387b6d2657410b2ef76ff2e32be
ENV DEBIAN_FRONTEND=noninteractive \
    SOFA_ROOT=/opt/sofa \
    VIRTUAL_ENV=/opt/mesh-venv
RUN apt-get update && apt-get install -y --no-install-recommends \
        bash ca-certificates curl unzip git procps python3.12 python3.12-venv libpython3.12 \
        libgl1 libopengl0 libglu1-mesa libgtk-3-0t64 libxft2 libxcursor1 \
        libxinerama1 libxext6 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN curl --fail --location --silent --show-error --retry 3 \
        "$SOFA_ZIP_URL" --output /tmp/sofa.zip \
    && echo "$SOFA_ZIP_SHA256  /tmp/sofa.zip" | sha256sum --check - \
    && mkdir -p /tmp/sofa \
    && unzip -q /tmp/sofa.zip -d /tmp/sofa \
    && mv /tmp/sofa/* /opt/sofa \
    && rm -rf /tmp/sofa /tmp/sofa.zip

ENV PATH="/opt/mesh-venv/bin:/opt/sofa/bin:${PATH}" \
    LD_LIBRARY_PATH="/opt/sofa/lib:/opt/sofa/plugins/SoftRobots/lib" 

    RUN python3.12 -m venv /opt/mesh-venv \
    && python -m pip install --no-cache-dir gmsh==4.15.2 numpy==2.5.3 \
    && printf '%s\n' \
        /opt/sofa/plugins/SofaPython3/lib/python3/site-packages \
        /opt/sofa/plugins/STLIB/lib/python3/site-packages \
        /opt/sofa/plugins/SoftRobots/lib/python3/site-packages \
        > /opt/mesh-venv/lib/python3.12/site-packages/sofa-plugins.pth

# Remove completed SOFA examples so the agent receives no tutorial solution.
RUN python -c "import shutil; from pathlib import Path; [shutil.rmtree(p) for p in Path('/opt/sofa').glob('**/share/sofa/examples')]" \
    && useradd --create-home --uid 10001 candidate

# Fail the build if the installed mesh tools or SOFA bindings cannot load.
RUN python -I -c 'import gmsh, numpy, Sofa, Sofa.Simulation, SofaRuntime, stlib3, splib3; SofaRuntime.importPlugin("SoftRobots")'
COPY SurfacePressureConstraint_Accordion.py run_scene.py LICENSE /app/
WORKDIR /app
