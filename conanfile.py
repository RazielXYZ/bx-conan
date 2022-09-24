from enum import auto
from conans import ConanFile, tools, MSBuild, AutoToolsBuildEnvironment
from pathlib import Path
import os

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

    invalidPackageExceptionText = "Less lib files found for copy than expected. Aborting."
    expectedNumLibs = 1
    bxFolder = "bx"
    

    vsVerToGenie = {"17": "2022", "16": "2019", "15": "2017"}

    gccOsToGenie = {"Windows": "--gcc=mingw-gcc", "Linux": "--gcc=linux-gcc", "Macos": "--gcc=osx", "Android": "--gcc=android", "iOS": "--gcc=ios"}
    gmakeOsToProj = {"Windows": "mingw", "Linux": "linux", "Macos": "osx", "Android": "android", "iOS": "ios"}
    gmakeArchToGenieSuffix = {"x86": "-x86", "x86_64": "-x64", "armv8": "-arm64", "armv7": "-arm"}
    osToUseArchConfigSuffix = {"Windows": False, "Linux": False, "Macos": True, "Android": True, "iOS": True}

    buildTypeToMakeConfig = {"Debug": "config=debug", "Release": "config=release"}
    archToMakeConfigSuffix = {"x86": "32", "x86_64": "64"}
    osToUseMakeConfigSuffix = {"Windows": True, "Linux": True, "Macos": False, "Android": False, "iOS": False}

    def configure(self):
        if self.settings.os == "Windows":
            if self.options.shared:
                self.libExt = ["*.dll"]
            else:
                self.libExt = ["*.lib"]
            self.libExt.extend(["*.pdb"])
            self.packageLibExt = ""
            self.binFolder = "windows"
        elif self.settings.os == "Linux":
            if self.options.shared:
                self.libExt = ["*.so"]
            else:
                self.libExt = ["*.a"]
            self.packageLibExt = ".a"
            self.binFolder = "linux"
        self.toolsFolder = cwd=os.path.sep.join([".", "tools", "bin", self.binFolder])

    def set_version(self):
        self.output.info("Setting version from git.")
        tools.rmdir(self.bxFolder)
        git = tools.Git(folder=self.bxFolder)
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
        genie = os.path.sep.join([self.toolsFolder, "genie"])
        if self.settings.compiler == "Visual Studio":
            # Use genie directly, then msbuild on specific projects based on requirements
            genieGen = f"vs{self.vsVerToGenie[str(self.settings.compiler.version)]}"
            self.output.highlight(genieGen)
            self.run(f"{genie} {genieGen}", cwd=self.bxFolder)
            msbuild = MSBuild(self)
            msbuild.build(f"{self.bxFolder}\\.build\\projects\\{genieGen}\\bx.vcxproj")
        else:
            # Not sure if XCode can be spefically handled by conan for building through, so assume everything not VS is make
            # Use genie with gmake gen, then make on specific projects based on requirements
            # gcc-multilib and g++-multilib required for 32bit cross-compilation, should see if we can check and install through conan
            
            # Generate projects through genie
            genieGen = f"{self.gccOsToGenie[str(self.settings.os)]} gmake"
            self.run(f"{genie} {genieGen}", cwd=self.bxFolder)

            # Build project folder and path from given settings
            projFolder = f"gmake-{self.gmakeOsToProj[str(self.settings.os)]}"
            if self.osToUseArchConfigSuffix[str(self.settings.os)]:
                projFolder += self.gmakeArchToGenieSuffix[str(self.settings.arch)]
            projPath = os.path.sep.join([".", self.bxFolder, ".build", "projects", projFolder])

            autotools = AutoToolsBuildEnvironment(self)
            with tools.environment_append(autotools.vars):
                # Build make args from settings
                conf = self.buildTypeToMakeConfig[str(self.settings.build_type)]
                if self.osToUseMakeConfigSuffix[str(self.settings.os)]:
                    conf += self.archToMakeConfigSuffix[str(self.settings.arch)]

                # Compile with make
                self.run(f"make {conf}", cwd=projPath)

    def package(self):
        # Copy includes
        self.copy("*.h", dst="include", src=f"{self.bxFolder}/include/")
        self.copy("*.inl", dst="include", src=f"{self.bxFolder}/include/")
        # Copy libs and debug info
        if len(self.copy(self.libExt[0], dst="lib", src=f"{self.bxFolder}/.build/", keep_path=False))  < self.expectedNumLibs:
            raise Exception(self.invalidPackageExceptionText)
        # Debug info files are optional, so no checking
        if len(self.libExt) > 1:
            for ind in range(1, len(self.libExt)):
                self.copy(self.libExt[ind], dst="lib", src=f"{self.bxFolder}/.build/", keep_path=False)
        for bxFile in Path(f"{self.package_folder}/lib").glob("*bx*"):
            tools.rename(f"{self.package_folder}/lib/{bxFile.name}", f"{self.package_folder}/lib/bx{bxFile.suffix}")

    def package_info(self):
        self.cpp_info.includedirs = ["include"]
        self.cpp_info.libs = [f"bx{self.packageLibExt}"]

        if self.settings.build_type == "Release":
            self.cpp_info.defines.extend(["BX_CONFIG_DEBUG=0"])
        elif self.settings.build_type == "Debug":
            self.cpp_info.defines.extend(["BX_CONFIG_DEBUG=1"])
        
        if self.settings.os == "Windows":
            if self.settings.arch == "x86":
                    self.cpp_info.system_libs.extend(["psapi"])
            if self.settings.compiler == "Visual Studio":
                self.cpp_info.includedirs.extend(["include/compat/msvc"])
                self.cpp_info.cxxflags.extend(["/Zc:__cplusplus"])
            else:
                self.cpp_info.includedirs.extend(["include/compat/mingw"])
        elif self.settings.os == "Linux":
            self.cpp_info.system_libs.extend(["pthread"])
            self.cpp_info.includedirs.extend(["include/compat/linux"])

