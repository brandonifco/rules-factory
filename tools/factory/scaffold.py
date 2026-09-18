"""The scaffold: the files that are the factory's build policy (managed) and the files that
become the engine's own on the first produce (engine-owned).

Neither kind may say anything the factory's inputs decide -- that is `pins.py`'s job. A managed
file is one fixed sequence of bytes per recipe version, so ownership.py can tell an engine's hand
edit from a recipe that moved; an engine-owned file is written only when absent, so a second
produce never undoes an edit to it.

global.json's SDK version is the kernel's toolchain and is managed, not generated: the SDK is
not a package the build restores, and an engine that must move it adopts the file.
"""
import json

import agentrails
import ownership
import pins

# No double hyphen in this text: it goes inside XML comments, where "--" is not allowed.
MANAGED_NOTE = ("Managed by rules-factory (recipe {version}): `factory produce` updates this file when its\n"
                "       recipe changes and refuses to overwrite a hand edit; adopting it makes it the engine's own.")


def managed_files():
    """The managed recipes (ownership.py): path -> text. Independent of the engine and the map, so
    each recipe version is one fixed sequence of bytes."""
    versions = {row.pattern: row.recipe for row in ownership.managed_rows("")}
    return {
        **agentrails.rails_files(),
        "global.json": json.dumps({"sdk": {"version": pins.SDK_VERSION, "rollForward": "disable"}}, indent=2) + "\n",
        "NuGet.config": (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<!-- Restore talks to nuget.org and nothing else; packages.lock.json pins every content hash.\n"
            f"     {MANAGED_NOTE.format(version=versions['NuGet.config'])} -->\n"
            "<configuration>\n"
            "  <packageSources>\n"
            "    <clear />\n"
            '    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />\n'
            "  </packageSources>\n"
            "  <packageSourceMapping>\n"
            '    <packageSource key="nuget.org">\n'
            '      <package pattern="*" />\n'
            "    </packageSource>\n"
            "  </packageSourceMapping>\n"
            "</configuration>\n"),
        "Directory.Build.props": (
            "<Project>\n\n"
            "  <!-- Zero-warning, deterministic builds.\n"
            f"       {MANAGED_NOTE.format(version=versions['Directory.Build.props'])} -->\n"
            "  <PropertyGroup>\n"
            "    <TargetFrameworks>net8.0;net10.0</TargetFrameworks>\n"
            "    <LangVersion>latest</LangVersion>\n"
            "    <Nullable>enable</Nullable>\n"
            "    <ImplicitUsings>enable</ImplicitUsings>\n"
            "    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>\n"
            "    <AnalysisLevel>latest</AnalysisLevel>\n"
            "    <EnableNETAnalyzers>true</EnableNETAnalyzers>\n"
            "    <EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>\n"
            "    <Deterministic>true</Deterministic>\n"
            "    <ContinuousIntegrationBuild Condition=\"'$(CI)' == 'true'\">true</ContinuousIntegrationBuild>\n"
            "    <InvariantGlobalization>true</InvariantGlobalization>\n"
            "    <GenerateDocumentationFile>true</GenerateDocumentationFile>\n"
            "  </PropertyGroup>\n\n"
            "  <!-- Every package, the map included, is pinned by content hash in packages.lock.json;\n"
            "       CI restores in locked mode. -->\n"
            "  <PropertyGroup>\n"
            "    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>\n"
            "    <RestoreLockedMode Condition=\"'$(CI)' == 'true'\">true</RestoreLockedMode>\n"
            "  </PropertyGroup>\n\n"
            "</Project>\n"),
    }


def engine_owned(model):
    """The engine-owned scaffold (ownership.py): path -> text, written only when absent."""
    name = model.name
    packages = "\n".join(f'    <PackageVersion Include="{p}" Version="{v}" />' for p, v in pins.TEST_PACKAGES)
    return {
        "Directory.Packages.props": (
            "<Project>\n\n"
            "  <PropertyGroup>\n"
            "    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>\n"
            "    <CentralPackageTransitivePinningEnabled>true</CentralPackageTransitivePinningEnabled>\n"
            "  </PropertyGroup>\n\n"
            "  <!-- The kernel and map pins, and the reference to the map, are rewritten by every\n"
            "       `factory produce`: they are facts about what the engine was produced from. -->\n"
            f'  <Import Project="$(MSBuildThisFileDirectory){pins.PACKAGES_PROPS}" />\n\n'
            "  <ItemGroup>\n"
            f"{packages}\n"
            "  </ItemGroup>\n\n"
            "</Project>\n"),
        f"{name}.slnx": (
            "<Solution>\n"
            f'  <Project Path="src/{name}/{name}.csproj" />\n'
            f'  <Project Path="tests/{name}.Tests/{name}.Tests.csproj" />\n'
            "</Solution>\n"),
        f"src/{name}/{name}.csproj": (
            '<Project Sdk="Microsoft.NET.Sdk">\n\n'
            "  <ItemGroup>\n"
            '    <PackageReference Include="RulesKernel" />\n'
            f"    <!-- The map package is referenced from {pins.PACKAGES_PROPS}, which `factory produce`\n"
            "         rewrites, so the reference always names the package the code was generated from. -->\n"
            "  </ItemGroup>\n\n"
            "  <ItemGroup>\n"
            "    <!-- What this engine was produced from (tools/factory/provenance.py); a generated test\n"
            "         asserts the embedded copy is the file. -->\n"
            f'    <EmbeddedResource Include="../../provenance.json" LogicalName="{name}.provenance.json" Link="provenance.json" />\n'
            "  </ItemGroup>\n\n"
            "</Project>\n"),
        f"tests/{name}.Tests/{name}.Tests.csproj": (
            '<Project Sdk="Microsoft.NET.Sdk">\n\n'
            "  <PropertyGroup>\n"
            "    <IsPackable>false</IsPackable>\n"
            "    <IsTestProject>true</IsTestProject>\n"
            "    <!-- Test names are the documentation here. -->\n"
            "    <GenerateDocumentationFile>false</GenerateDocumentationFile>\n"
            "  </PropertyGroup>\n\n"
            "  <ItemGroup>\n"
            + "".join(f'    <PackageReference Include="{p}" />\n' for p, _ in pins.TEST_PACKAGES) +
            "  </ItemGroup>\n\n"
            "  <ItemGroup>\n"
            f'    <ProjectReference Include="../../src/{name}/{name}.csproj" />\n'
            "  </ItemGroup>\n\n"
            "</Project>\n"),
        agentrails.AGENT_POLICY: agentrails.agent_policy(),
    }
