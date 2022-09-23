from conans import ConanFile, tools, MSBuild
from pathlib import Path

required_conan_version = ">=1.50.0"


class bxConan(ConanFile):
    name = "bx"
    license = "BSD-2-Clause"
    homepage = "https://github.com/bkaradzic/bx"
    url = "https://github.com/RazielXYZ/bx-conan"
    description = "Base library providing utility functions and macros."
    topics = ("lib-static", "C++", "C++14", "general", "utility")
    settings = "os", "compiler", "arch", "build_type"
    options = {"shared": [True, False]}
    default_options = {"shared": False}
    generators = "json"

    invalidPackageExceptionText = "Less lib files found for copy than expected. Aborting."
    expectedNumLibs = 1
    bxFolder = "bx"

    vsVerToGenie = {"17": "2022", "16": "2019", "15": "2017"}

    def set_version(self):
        self.output.info("Setting version from git.")
        git = tools.Git(folder=self.bxFolder)
        if not git.check_repo:
            git.clone(f"{self.homepage}.git", "master")
        # Hackjob semver! Versioning by commit seems rather annoying for users, so let's version by commit count
        numCommits = int(git.run("rev-list --count master"))
        verMajor = 1 + (numCommits // 10000)
        verMinor = (numCommits // 100) % 100
        verRev = numCommits % 100
        self.output.highlight(f"Version {verMajor}.{verMinor}.{verRev}")
        self.version = f"{verMajor}.{verMinor}.{verRev}"

    def source(self):
        self.output.info("Getting source")
        git = tools.Git(folder=self.bxFolder)
        git.clone(f"{self.homepage}.git", "master")

    def build(self):
        # Map conan compilers to genie input
        if self.settings.os == "Windows":
            if self.settings.compiler == "Visual Studio":
                # Use genie directly, then msbuild
                genieGen = f"vs{self.vsVerToGenie[str(self.settings.compiler.version)]}"
                self.output.highlight(genieGen)
                self.run(f"cd {self.bxFolder} && .\\tools\\bin\\windows\\genie.exe {genieGen}")
                msbuild = MSBuild(self)
                msbuild.build(f"{self.bxFolder}\\.build\\projects\\{genieGen}\\bx.vcxproj")
            else:
                # Run make in mingw mode?
                self.output.info("mingw")
        else:
            # Use make, which will use genie for us
            # Gotta make sure cross-compilation (from 64 to 32 bit) works properly though
            self.output.info("linux/mac")

    def package(self):
        # Copy includes
        self.copy("*.h", dst="include", src=f"{self.bxFolder}/include/")
        self.copy("*.inl", dst="include", src=f"{self.bxFolder}/include/")
        # Copy libs and debug info
        if len(self.copy("*.lib", dst="lib", src=f"{self.bxFolder}/.build/", keep_path=False))  < self.expectedNumLibs:
            raise Exception(self.invalidPackageExceptionText)
        self.copy("*.pdb", dst="lib", src=f"{self.bxFolder}/.build/", keep_path=False)
        for bxFile in Path(f"{self.package_folder}/lib").glob("bx*"):
            tools.rename(f"{self.package_folder}/lib/{bxFile.name}", f"{self.package_folder}/lib/bx{bxFile.suffix}")

    def package_info(self):
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libs = ["bx"]

        if self.settings.build_type == "Release":
            self.cpp_info.defines.extend(["BX_CONFIG_DEBUG=0"])
        elif self.settings.build_type == "Debug":
            self.cpp_info.defines.extend(["BX_CONFIG_DEBUG=1"])
        
        if self.settings.os == "Windows":
            if self.settings.compiler == "Visual Studio":
                self.cpp_info.includedirs.extend(["include/compat/msvc"])
                self.cpp_info.cxxflags.extend(["/Zc:__cplusplus"])
                if self.settings.arch == "x86":
                    self.cpp_info.libs.extend(["psapi"])
