// Thin adapter over LabRecorder's native LSL/XDF engine. No Qt or server.
#include "recording.h"
#include <filesystem>
#ifdef _WIN32
#include <windows.h>
#endif

int record(const std::string &path) {
    try {
        if (std::filesystem::exists(std::filesystem::u8path(path)))
            throw std::runtime_error("Output file already exists");
        // One watchlist records current and future streams without duplicates.
        recording session(path, {}, {"true()"}, {}, true);
        std::cin.get(); // Parent owns this private pipe; EOF also finalizes XDF.
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "RESPIRA_RECORDER_ERROR " << error.what() << std::endl;
        return 1;
    }
}

#ifdef _WIN32
int wmain(int argc, wchar_t **argv) {
    if (argc != 2) return 2;
    int bytes = WideCharToMultiByte(CP_UTF8, 0, argv[1], -1, nullptr, 0, nullptr, nullptr);
    if (!bytes) return 2;
    std::string path(bytes, '\0');
    WideCharToMultiByte(CP_UTF8, 0, argv[1], -1, path.data(), bytes, nullptr, nullptr);
    path.pop_back();
    return record(path);
}
#else
int main(int argc, char **argv) { return argc == 2 ? record(argv[1]) : 2; }
#endif
