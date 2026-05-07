# MIGraphX MXR Inspector

A small C++ utility to inspect compiled MIGraphX (`.mxr`) files, specifically designed for darktable AI cache files.

## Features
- **Extract Model Names:** Attempts to identify the model type from internal parameter paths.
- **Shape Analysis:** Lists all input/output shapes and types required for recompilation.
- **Batch Processing:** Inspect a single file or an entire directory.
- **Instruction Stream:** Optional verbose mode to see the full compiled kernel sequence.

## Prerequisites
- `libmigraphx-dev`
- `cmake`
- C++17 compatible compiler

## Build
```bash
mkdir build && cd build
cmake ..
make
```

## Usage
```bash
# Inspect all files in darktable cache
./inspect_mxr ~/.cache/darktable/ai/amd/migraphx

# Inspect a specific file with full instruction details
./inspect_mxr -v /path/to/model.mxr

# Help
./inspect_mxr --help
```
