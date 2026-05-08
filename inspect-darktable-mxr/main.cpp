#include <iostream>
#include <vector>
#include <string>
#include <filesystem>
#include <algorithm>
#include <migraphx/program.hpp>
#include <migraphx/load_save.hpp>
#include <migraphx/shape.hpp>
#include <migraphx/version.h>
#include <migraphx/value.hpp>
#include <migraphx/module.hpp>

// Macros to convert numeric version to string safely
#define STRINGIFY(x) #x
#define TOSTRING(x) STRINGIFY(x)

namespace fs = std::filesystem;

void print_help(const char* prog_name) {
    std::cout << "Usage: " << prog_name << " [options] <sourcedir|mxr_file>\n\n"
              << "Options:\n"
              << "  -h, --help     Show this help message\n"
              << "  -v, --verbose  Show full instruction stream\n\n"
              << "Arguments:\n"
              << "  sourcedir      Directory containing .mxr files (usually ~/.cache/darktable/ai/amd/migraphx)\n"
              << "  mxr_file       [Or] path to a single .mxr file\n";
}

std::string find_model_name(const migraphx::program& p) {
    // 1. Check Parameter Names (Most reliable for Darktable/ONNX models)
    auto param_names = p.get_parameter_names();
    for (const auto& name : param_names) {
        // Darktable models often use /layer/ paths
        if (name.size() > 1 && name[0] == '/') {
            size_t second_slash = name.find('/', 1);
            if (second_slash != std::string::npos) {
                return name.substr(1, second_slash - 1);
            }
            return name.substr(1);
        }
    }
    
    // 2. Check for internal program attributes
    migraphx::value v = p.to_value();
    if (v.contains("name")) return v.at("name").to<std::string>();
    
    // 3. Fallback to main module name
    const auto* mm = p.get_main_module();
    if (mm != nullptr) {
        std::string mod_name = mm->name();
        if (mod_name != "main" && !mod_name.empty()) return mod_name;
    }

    return "unknown_model";
}

void inspect_file(const std::string& filename, bool verbose) {
    try {
        // Load the binary optimized graph
        migraphx::program p = migraphx::load(filename);
        std::string model_name = find_model_name(p);

        std::cout << "====================================================\n";
        std::cout << "FILE: " << fs::path(filename).filename().string() << "\n";
        std::cout << "----------------------------------------------------\n";
        std::cout << "Inferred Name: " << model_name << "\n";
        
        // Use the stringified version macro to avoid literal errors
        std::cout << "MIGraphX Ver:  " << TOSTRING(MIGRAPHX_VERSION) << "\n";
        std::cout << "Is Compiled:   " << (p.is_compiled() ? "Yes" : "No") << "\n";
        
        std::cout << "\n[Inputs/Parameters]\n";
        auto param_shapes = p.get_parameter_shapes();
        if (param_shapes.empty()) {
            std::cout << "  (No parameters found)\n";
        } else {
            for (const auto& [name, shape] : param_shapes) {
                std::cout << "  - " << name << ": " << shape << "\n";
            }
        }

        std::cout << "\n[Outputs]\n";
        auto output_shapes = p.get_output_shapes();
        for (size_t i = 0; i < output_shapes.size(); ++i) {
            // Display output shapes stored in the program
            std::cout << "  - output_" << i << ": " << output_shapes[i] << "\n";
        }

        if (verbose) {
            std::cout << "\n[Instruction Stream]\n";
            // Dumps the MIGraphX Intermediate Representation
            p.debug_print();
        }
        std::cout << "====================================================\n\n";

    } catch (const std::exception& e) {
        std::cerr << "Error inspecting " << filename << ": " << e.what() << "\n\n";
    }
}

int main(int argc, char** argv) {
    bool verbose = false;
    std::string source;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-h" || arg == "--help") {
            print_help(argv[0]);
            return 0;
        } else if (arg == "-v" || arg == "--verbose") {
            verbose = true;
        } else if (source.empty()) {
            source = arg;
        }
    }

    if (source.empty()) {
        print_help(argv[0]);
        return 1;
    }

    if (fs::is_directory(source)) {
        for (const auto& entry : fs::directory_iterator(source)) {
            if (entry.path().extension() == ".mxr") {
                inspect_file(entry.path().string(), verbose);
            }
        }
    } else if (fs::is_regular_file(source)) {
        inspect_file(source, verbose);
    } else {
        std::cerr << "Error: Source not found.\n";
        return 1;
    }

    return 0;
}
