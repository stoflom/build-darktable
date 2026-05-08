# Darktable Build Automator

This repository contains a specialized build script, `build_darktable.sh`, designed to automate the process of updating the darktable source code and building it with a specific, pre-configured set of features and installation parameters. This script is for users who are eager to try the latest-and-greatest. You should also be comfortable with software development tools and installing applications from the linux commandline.

This will install the latest---as yet unreleased---build from the darktable developers. There is no guarantee that this code will be functional. Also installing this may **DESTROY ANY EXISTING DARKTABLE** installation you already have. Refer to the darktable documentation if you want to install this side-by-side to an existing installation. Or preferably, install it in a separate environment using `boxes`. Do not use `toolbox` since your HOME space is retained. In any case, make a backup of you HOME space.

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

After building and installing the first time (only needed once) you must create symbolic links to make the new binaries visible in your command path and also the icon in your desktop. The script scans `/opt/darktable` subdirectories and creates the required links automatically (You will be prompted for the sudo password.):
```bash
./make-links.sh
```

# Running AI models

The options above include the enable-ai flag which is required to use the new ai denoising, mask generation and upscaling features of darktable which have not yet been released.

## onnxruntime CPU provider

Works out-of-the-box after installing and using the darktable provided onnxruntime, or the fedora repo package. Also works with a self compiled onnxruntime, see below. The fedora supplied onnxruntime package is restricted to running on the cpu and will not use a gpu.

## MIGraphX provider under fedora44

If the ROCm, hip, miopen and migraphix AMD supplied libraries in fedora44 repository are installed, onnxruntime can be compiled to use migraphx for your specific cpu and gpu. (Refer https://github.com/stoflom/onnxruntime). The compiled onnxruntime can then be selected in darktable->preferences->ai submenu. The darktable developers have also created a script to install a pre-compiled onnxruntime with migraphx enabled, see darktable tools/ai/README.md.

With onnxruntime and the migraphx execution provider on my AMD Ryzen Pro 9 8945HS ai is sped up about 10 times compared to the cpu provider. However, initially compiling the onnx kernels takes a very long time > 40min for the raw denoise. The kernels are compiled when first used; a process which makes darktable appear to be frozen. It is better to run darktable from the commandline to initially compile the migraphix kernels so that progress can be monitored.
```bash
darktable -d ai
```
Saving the compiled kernels in a cache is essential for future use. darktable sets environment variables for the cache directories when migraphx is enabled. They can also be set manually when starting darktable from the commandline (setenv.sh):
```bash
#Set miopen cache directory
export MIOPEN_USER_DB_PATH='/home/<user>/.cache/darktable/ai/amd/miopen'
export MIOPEN_CUSTOM_CACHE_DIR='/home/<user>/.cache/darktable/ai/amd/miopen'
#Set migraphx cache directory
export ORT_MIGRAPHX_MODEL_CACHE_PATH='/home/<user>/.cache/darktable/ai/amd/migraphx'
# Allow migraphx to compile with all cores will provide some speedup of the first-use.
export MIGRAPHX_GPU_COMPILE_PARALLEL="$(nproc)"
```

When all goes well the kernels (mxr files) will be created under /home/<user>/.cache/darktable/ai/amd/migraphx for your specific use cases. They will enable very efficient processing of the ai models on your hardware. NOTE you may need a good amount of memory: on my fedora setup with total shared RAM 64GB, the migraphx compile process showed memory use up to about 10GB VRAM and about 4-5GB when running the pre-compiled mxr kernels. This is the total memory used by the system without much else running in user space.
