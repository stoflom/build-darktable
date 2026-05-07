#Set miopen cache directory
export MIOPEN_USER_DB_PATH='/home/<user>/.cache/darktable/ai/amd/miopen'
export MIOPEN_CUSTOM_CACHE_DIR='/home/<user>/.cache/darktable/ai/amd/miopen'
#Set migraphx cache directory
export ORT_MIGRAPHX_MODEL_CACHE_PATH='/home/<user>/.cache/darktable/ai/amd/migraphx'
# Allow migraphx to compile with all cores will provide some speedup of the first-use compile process.
export MIGRAPHX_GPU_COMPILE_PARALLEL="$(nproc)"
