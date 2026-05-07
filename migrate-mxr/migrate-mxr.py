import onnx
import onnxruntime as ort
import os
import sys
import argparse
import numpy as np

def recompile_darktable_models(onnx_root, target_dir, use_fp16=False):
    onnx_root = os.path.expanduser(onnx_root)
    target_dir = os.path.expanduser(target_dir)

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    print(f"[*] Scanning models in: {onnx_root}")
    print(f"[*] Target Directory: {target_dir}")
    print(f"[*] Mode: {'FP16' if use_fp16 else 'FP32'}")

    for root, dirs, files in os.walk(onnx_root):
        onnx_files = sorted([f for f in files if f.endswith('.onnx')])
        if not onnx_files:
            continue
        folder_name = os.path.basename(root)
        for onnx_file in onnx_files:
            model_name = f"{folder_name}/{onnx_file}"
            onnx_path = os.path.join(root, onnx_file)

            print(f"\n>>> Compiling: {model_name}")

            # 1. Setup MIGraphX Provider
            nproc = os.cpu_count() or 1
            os.environ["MIGRAPHX_GPU_COMPILE_PARALLEL"] = str(nproc)

            providers = [
                ('MIGraphXExecutionProvider', {
                    'device_id': 0,
                    'migraphx_fp16_enable': 1 if use_fp16 else 0,
                    'migraphx_model_cache_dir' : target_dir
                }),
                'CPUExecutionProvider'
            ]

            try:
                # 2. Load ONNX model directly to inspect shapes accurately
                onnx_model = onnx.load(onnx_path)
                
                # 3. Load Session
                session = ort.InferenceSession(onnx_path, providers=providers)

                # 4. Create Dummy Inputs based on ONNX metadata
                feeds = {}
                for input_tensor in onnx_model.graph.input:
                    name = input_tensor.name
                    shape = []
                    
                    # Iterate through the dimensions of the input
                    dim_idx = 0
                    for dim in input_tensor.type.tensor_type.shape.dim:
                        if dim.HasField('dim_value') and dim.dim_value > 0:
                            shape.append(dim.dim_value)
                        else:
                            param = dim.dim_param.lower() if dim.HasField('dim_param') else ''
                            # Use sensible defaults for dynamic dims
                            if 'batch' in param:
                                shape.append(1)
                            elif 'height' in param or param == 'h':
                                shape.append(64)
                            elif 'width' in param or param == 'w':
                                shape.append(64)
                            elif 'num_points' in param:
                                shape.append(1)
                            else:
                                # positional heuristic for NCHW layout
                                shape.append(64 if dim_idx >= 2 else 1)
                        dim_idx += 1
                    
                    print(f"    Input '{name}' using shape: {shape}")

                    # Use float32 as the default for Darktable models
                    dtype = np.float32 
                    feeds[name] = np.zeros(shape, dtype=dtype)

                # 5. Execute one "Warmup" run
                session.run(None, feeds)
                print(f"    [SUCCESS] Compiled and cached in: {target_dir}")

            except Exception as e:
                print(f"    [ERROR] Could not compile {model_name}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Darktable AI Model Recompiler")
    parser.add_argument("onnx_source", help="Path to ~/.local/share/darktable/models/")
    parser.add_argument("output_dir", help="Where to save the newly compiled .mxr files")
    parser.add_argument("--fp16", action="store_true", help="Enable FP16 precision")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    recompile_darktable_models(args.onnx_source, args.output_dir, args.fp16)
