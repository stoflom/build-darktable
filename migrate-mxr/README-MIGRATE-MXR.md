# Darktable MIGraphX Model Recompiler

**THIS IS WIP IT IS NOT YET USEFUL**

Compiles ONNX models into MIGraphX (`.mxr`) binaries for your GPU using ONNX Runtime with the MIGraphX Execution Provider. This script will take a significant time to run, probably above 30m, depending on your hardware.

## Usage

```bash
python migrate-mxr-fixed.py <onnx_source> <output_dir> [--fp16]
```

- `onnx_source` — Path to (folder containing model subdirectories with `.onnx` files (for darktable usually  `~/.local/share/darktable/models/`)
- `output_dir` — Where to save the newly compiled `.mxr` files
- `--fp16` — Enable FP16 precision (default: FP32, FP16 may reduce your memory usage and increase processing speed with little quality loss.)

### Example

To recompile all darktable ai models and place the in subdirectory `compiled-mxr`
:
```bash
python migrate-mxr-fixed.py ~/.local/share/darktable/models/ compiled-mxr
```

## How it works

1. Scans the ONNX source directory recursively for all `.onnx` files
2. Loads each model and inspects its input shapes from ONNX metadata
3. Creates dummy inputs with appropriate shapes (sensible defaults for dynamic dimensions)
4. Creates an ONNX Runtime inference session with the `MIGraphXExecutionProvider`, which triggers GPU compilation and caches the compiled `.mxr` file to the output directory
5. Runs a warmup inference pass to finalize the cache

## Why this is needed

onnxruntime with the MIGRaphX provider for AMD GPU's takes a while to initially compile models using an exhaustive optimization search. The pre-compiled mxr files are then used to avoid recompilation delays at runtime. These files contain GPU-specific machine code. When moving to a different GPU model or updating ROCm/MIGraphX, the old `.mxr` files may need to be regenerated from the original ONNX sources.

## Dynamic shape handling

Models with dynamic dimensions (e.g. variable batch size, height, width) are given sensible defaults:

| Dimension | Default |
|-----------|---------|
| `batch`, `batch_size` | `1` |
| `height`, `h` | `64` |
| `width`, `w` | `64` |
| `num_points` | `1` |
| Other dynamic dims | `1` (or `64` for positional dim 2/3 in NCHW layout) |

## Requirements

- `onnx`
- `onnxruntime` with MIGraphX EP (`onnxruntime-migraphx`)
- ROCm/MIGraphX runtime

## The MIGraphX cache
After running this script the created mxr files must be moved to the cache where the onnxruntime will expect them to be.
The location of the cache is specified in an environment variable which must be set before the model is loaded.  E.G. darktable sets the following variable:

```bash
#Set migraphx cache directory
export ORT_MIGRAPHX_MODEL_CACHE_PATH='/home/<user>/.cache/darktable/ai/amd/migraphx'
```
The pre-compiled mxr files must be moved to the location specified by ORT_MIGRAPHX_MODEL_CACHE_PATH after running this script. Make sure to backup your old cache in case you want to roll-back.

Be aware that the mxr files created by this script is based on guesses from the models. Additional mxr files may still be created by onnxruntime during firts use, according to the shapes required. Some models may also fail to compile, e.g. if you compile for FP16 quantization. They will then be correctly compiled when the model is first used.

NOTE: I am unable to test this on many GPU's so there is **no guarantee** that this may be of any use to you.
