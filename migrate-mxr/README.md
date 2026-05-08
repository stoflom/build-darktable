# Darktable MIGraphX Model Recompiler

Compiles ONNX models into MIGraphX (`.mxr`) binaries for your GPU using ONNX Runtime with the MIGraphX Execution Provider. This script will take a significant time to run, probably above 30m, depending on your hardware.

> **Tip:** Use `list-onnxshapes.py` to quickly inspect ONNX models (inputs, outputs, shapes, ops) without triggering GPU compilation. See [ONNX Model Inspector](#onnx-model-inspector).

## Table of Contents

- [Usage](#usage)
- [How it works](#how-it-works)
- [Why this is needed](#why-this-is-needed)
- [Dynamic shape handling](#dynamic-shape-handling)
- [The MIGraphX cache](#the-migraphx-cache)
- [Requirements](#requirements)
- [ONNX Model Inspector](#onnx-model-inspector)

---

## Usage

```bash
python migrate-mxr-fixed.py <onnx_source> <output_dir> [--fp16]
```

- `onnx_source` — Path to folder containing model subdirectories with `.onnx` files (for darktable usually `~/.local/share/darktable/models/`)
- `output_dir` — Where to save the newly compiled `.mxr` files
- `--fp16` — Enable FP16 precision (default: FP32, FP16 may reduce your memory usage and increase processing speed with little quality loss.)

### Example

To recompile all darktable AI models and place them in subdirectory `compiled-mxr`:

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

ONNX Runtime with the MIGraphX provider for AMD GPUs takes a while to initially compile models using an exhaustive optimization search. The pre-compiled `.mxr` files are then used to avoid recompilation delays at runtime. These files contain GPU-specific machine code. When moving to a different GPU model or updating ROCm/MIGraphX, the old `.mxr` files may need to be regenerated from the original ONNX sources.

## Dynamic shape handling

Models with dynamic dimensions (e.g. variable batch size, height, width) are given sensible defaults:

| Dimension | Default |
|-----------|---------|
| `batch`, `batch_size` | `1` |
| `height`, `h` | `64` |
| `width`, `w` | `64` |
| `num_points` | `1` |
| Other dynamic dims | `1` (or `64` for positional dim 2/3 in NCHW layout) |

## The MIGraphX cache

After running this script the created `.mxr` files must be moved to the cache where ONNX Runtime will expect them. The location of the cache is specified in an environment variable which must be set before the model is loaded. E.g. darktable sets the following variable:

```bash
# Set migraphx cache directory
export ORT_MIGRAPHX_MODEL_CACHE_PATH='/home/<user>/.cache/darktable/ai/amd/migraphx'
```

The pre-compiled `.mxr` files must be moved to the location specified by `ORT_MIGRAPHX_MODEL_CACHE_PATH` after running this script. Make sure to backup your old cache in case you want to roll-back.

Be aware that the `.mxr` files created by this script are based on guesses from the models. Additional `.mxr` files may still be created by ONNX Runtime during first use, according to the shapes required. Some models may also fail to compile, e.g. if you compile for FP16 quantization. They will then be correctly compiled when the model is first used.

> **NOTE:** I am unable to test this on many GPUs so there is **no guarantee** that this may be of any use to you.

## Requirements

- `onnx`
- `onnxruntime` with MIGraphX EP (`onnxruntime-migraphx`)
- ROCm/MIGraphX runtime

---

## ONNX Model Inspector

`list-onnxshapes.py` — Quickly inspect ONNX model files without triggering GPU compilation. Reads graph metadata directly from the `.onnx` file using the `onnx` library — no `onnxruntime` needed.

### Usage

```bash
python list-onnxshapes.py [path] [--no-recursive]
```

- `path` — Path to a single `.onnx` file or a root directory (default: current directory)
- `--no-recursive` — Only scan the given directory, not subdirectories

#### Examples

```bash
# Single model
python list-onnxshapes.py ~/.local/share/darktable/models/denoise-nafnet/model.onnx

# Scan all models recursively (default)
python list-onnxshapes.py ~/.local/share/darktable/models/

# Current directory, non-recursive
python list-onnxshapes.py --no-recursive
```

### Output

For each model, prints:

| Section | Fields |
|---------|--------|
| Header | Model name, full path |
| Metadata | IrVersion, Producer, Version, DocString |
| Inputs | Name, Shape (dynamic dims shown as `-1`), Data type |
| Outputs | Name, Shape, Data type |
| Graph | Node count, op breakdown with counts, initializer count, total parameter elements |

#### Sample

```
============================================================
Model: model.onnx
Path:  /home/user/.local/share/darktable/models/denoise-nafnet/model.onnx
============================================================
IrVersion:  8
Producer:   pytorch
Version:    0
DocString:

--- Inputs (1) ---
  [0] Name:  input
      Shape: [-1, 3, -1, -1]
      Type:  FLOAT

--- Outputs (1) ---
  [0] Name:  output
      Shape: [-1, -1, -1, -1]
      Type:  FLOAT

--- Graph ---
  Nodes:        3683
  Ops:
    Constant: 1256
    Mul: 396
    Add: 293
    Conv: 226
    ...
  Initializers: 664
  Total param elements: 29,159,715
```

### Requirements

- Python 3.8+
- `onnx` (`pip install onnx`)
