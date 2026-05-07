#include <iostream>
#include <vector>
#include <string>
#include <filesystem>
#include <migraphx/program.hpp>
#include <migraphx/load_save.hpp>
#include <migraphx/shape.hpp>
#include <migraphx/version.h>
#include <migraphx/value.hpp>

namespace fs = std::filesystem;

void print_help(const char* prog_name) {
    std::cout << "Usage: " << prog_name << " [options] <sourcedir|mxr_file>\n\n"
              << "Options:\n"
              << "  -h, --help     Show this help message\n"
              << "  -v, --verbose  Show full instruction stream\n\n"
              << "Arguments:\n"
              << "  sourcedir      Directory containing .mxr files (usually ~/.cache/darktable/ai/amd/migraphx)\n"
              << "  mxr_file       Path to a single .mxr file\n";
}

std::string find_model_name(const migraphx::program& p) {
    auto param_names = p.get_parameter_names();
    for (const auto& name : param_names) {
        // Many models have a prefix like /image_encoder/ or /down1/
        if (name.size() > 1 && name[0] == '/') {
            size_t second_slash = name.find('/', 1);
            if (second_slash != std::string::npos) {
                return name.substr(1, second_slash - 1);
            }
            return name.substr(1);
        }
    }
    
    migraphx::value v = p.to_value();
    if (v.contains("name")) return v.at("name").to<std::string>();

    return "unknown";
}

void inspect_file(const std::string& filename, bool verbose) {
    try {
        migraphx::program p = migraphx::load(filename);
        std::string model_name = find_model_name(p);

        std::cout << "--- FILE: " << filename << " ---\n";
        std::cout << "Model Name: " << model_name << "\n";
        std::cout << "Is Compiled: " << (p.is_compiled() ? "Yes" : "No") << "\n";
        
        std::cout << "Shapes (Parameters):\n";
        auto param_shapes = p.get_parameter_shapes();
        for (const auto& [name, shape] : param_shapes) {
            std::cout << "  " << name << " -> " << shape << "\n";
        }

        std::cout << "Shapes (Outputs):\n";
        auto output_shapes = p.get_output_shapes();
        for (const auto& shape : output_shapes) {
            std::cout << "  " << shape << "\n";
        }

        if (verbose) {
            std::cout << "Instructions:\n";
            p.debug_print();
        }
        std::cout << "\n";

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
        std::cerr << "Error: Source '" << source << "' not found or not a valid directory/file.\n";
        return 1;
    }

    return 0;
}
