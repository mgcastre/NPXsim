# NPXsim

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

The **Neo-Panamax lock simulator (NPXsim)** is a model to simulate saltwater intrusion through the Neo-Panamax (NPX) locks of the Panama Canal. It consists of a mass balance that represents the exchanges of water and salt that take place between lock chambers and water saving basins (WSBs) as a result of vessel transit. 

In its current implementation, **NPXsim** is tailor-made to simulate the operations of the NPX locks. However, it is possible to adapt it for the simulation of lock operations in any three-steps lock system with or without the use of WSBs. 

## 🚧 Status: Under Construction
The documentation for this repository is currently being developed. Please check back soon for detailed usage guides, API references, and more comprehensive examples.

---

## 🚀 Installation Guide

This project uses [uv](https://docs.astral.sh/uv/) for environment and package management. 

1. Ensure you have `uv` installed. If not, you can install it by following the [official documentation](https://docs.astral.sh/uv/getting-started/installation/).

2. Clone this repository to a local directory:

```bash
git clone https://github.com/mgcastre/NPXsim.git
cd NPXsim
```

3. Use the following command to create a virtual environment and install all dependencies exactly as defined in the `uv.lock` file:

```bash
uv sync
```

4. Activate the isolated environment to start working:

**macOS/Linux:**

```bash
source .venv/bin/activate
```

**Windows:**

```bash
.venv\Scripts\activate
```

## 📖 Basic Usage

A minimal code example demonstrating how to initialize and run the NPXsim model is provided in the `examples` folder.

---

*Created as part of PhD Research at IHE Delft Institute for Water Education and TU Delft.*