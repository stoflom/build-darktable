# Darktable Build Automator

This repository contains a specialized build script, `build_darktable.sh`, designed to automate the process of updating the darktable source code and building it with a specific, pre-configured set of features and installation parameters. This script is for users who are eager to try the latest-and-greatest. You should also be comfortable with software development tools and installing applications from the Linux command line.

This will install the latest---as yet unreleased---build from the darktable developers. There is no guarantee that this code will be functional. Also installing this may **DESTROY ANY EXISTING DARKTABLE** installation you already have. Refer to the darktable documentation if you want to install this side-by-side to an existing installation. Or preferably, install it in a separate environment using `boxes`. Do not use `toolbox` since your HOME space is retained. In any case, make a backup of your HOME space.

## Purpose

The `build_darktable.sh` script is a wrapper around the official darktable `build.sh` script. Its primary goal is to:

1.  **Ensure consistency**: It uses a predefined set of build options (like `--enable-ai` and `--prefix /opt/darktable`) so that every build is reproducible and contains the required features.
2.  **Automate updates**: It automatically performs a `git pull --recurse-submodules` to ensure the build is always based on the latest available source code and submodules.
3.  **Guaranteed clean builds**: It automatically removes any existing build directory to prevent conflicts between previous builds and the current one.
4.  **Simplify the workflow**: Instead of remembering complex build flags or running multiple commands (pull, then build, then install), a single command handles the entire lifecycle.

## Prerequisites

Before running the script, ensure you have the following:

*   **Darktable Source**: The `darktable/` directory must exist in the same folder as the script.
*   **Dependencies**: The system must have all the necessary dependencies for building darktable (as required by the darktable `build.sh` script).
*   **Permissions**: Since the script uses the `--sudo` flag during installation, you must have sudo privileges on the system.

## Usage

To build and install darktable, simply execute the script from the root of this repository:

```bash
chmod +x build_darktable.sh
./build_darktable.sh
```

### Build Configuration

The build configuration is defined within the `BUILD_OPTIONS` array inside `build_darktable.sh`. You can modify this array to change the installation prefix, build type, or enabled features. To see the available options:

```bash
darktable/build.sh --help
```

Current default options:
*   `--prefix /opt/darktable`
*   `--build-type Release`
*   `--enable-ai`
*   `--install`
*   `--sudo`

## Creating symbolic links

After building and installing the first time (only needed once), you must create symbolic links to make the new binaries visible in your command path and the icon visible in your desktop. The script scans `/opt/darktable` subdirectories and creates the required links automatically (you will be prompted for the sudo password.):
```bash
./make-links.sh
```

## Running AI models

The options above include the `--enable-ai` flag, which is required to use the new AI denoising, mask generation, and upscaling features of darktable, which have been released in version 5.6.

## ONNX Runtime CPU Provider

Works out-of-the-box after installing and using the darktable-provided ONNX Runtime, or the Fedora repo package. Also works with a self-compiled ONNX Runtime (see below). The Fedora-supplied ONNX Runtime package is restricted to running on the CPU and will not use a GPU.

## MIGraphX provider under Fedora 44

If the ROCm, HIP, MiOS, and MIGraphX AMD-supplied libraries in the Fedora 44 repository are installed, ONNX Runtime can be compiled to use MIGraphX for your specific CPU and GPU. (See [https://github.com/stoflom/onnxruntime](https://github.com/stoflom/onnxruntime)). The compiled ONNX Runtime can then be selected in **Darktable → Preferences → AI** submenu. The darktable developers have also kindly created a script to install a pre-compiled ONNX Runtime with MIGraphX enabled; see `darktable/tools/ai/README.md`.

With ONNX Runtime and the MIGraphX execution provider, on my AMD Ryzen Pro 9 8945HS, AI is sped up about 10× compared to the CPU provider. However, initially compiling the ONNX kernels takes a very long time (>40 min for raw denoise). The kernels are compiled on first use, a process that makes darktable appear frozen. It is better to run darktable from the command line to compile the MIGraphX kernels initially so that progress can be monitored in the terminal.
```bash
darktable -d ai
```
Saving the compiled kernels in a cache is essential for future use. Darktable sets environment variables for the cache directories when MIGraphX is enabled. They can also be set manually when starting Darktable from the command line (`setenv.sh`):
```bash
#Set miopen cache directory
export MIOPEN_USER_DB_PATH='/home/<user>/.cache/darktable/ai/amd/miopen'
export MIOPEN_CUSTOM_CACHE_DIR='/home/<user>/.cache/darktable/ai/amd/miopen'
#Set migraphx cache directory
export ORT_MIGRAPHX_MODEL_CACHE_PATH='/home/<user>/.cache/darktable/ai/amd/migraphx'
# Allow migraphx to compile with all cores will provide some speedup of the first-use.
export MIGRAPHX_GPU_COMPILE_PARALLEL="$(nproc)"
```

When all goes well, the kernels (`.mxr` files) will be created under `/home/<user>/.cache/darktable/ai/amd/migraphx` for your specific use cases. They will enable very efficient processing of the AI models on your hardware. **Note:** you may need a good amount of memory: on my Fedora setup with 64 GB shared RAM, the MIGraphX compile process used up to about 10 GB VRAM and 4–5 GB when running the pre-compiled `.mxr` kernels. This is the total memory used by the system with little else running in user space.
