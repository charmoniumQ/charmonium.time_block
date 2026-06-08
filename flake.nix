{
  inputs = {
    nixpkgs = {
      url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    };
    flake-utils = {
      url = "github:numtide/flake-utils";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    ...
  }:
    flake-utils.lib.eachDefaultSystem
    (
      system: let
        pkgs = import nixpkgs { inherit system; };
        isPythonPackage = deriv: builtins.hasAttr "pythonPath" deriv;
        pyprojectToml = builtins.fromTOML (builtins.readFile ./pyproject.toml);
        nativeCheckInputs = pypkgs: [
          pypkgs.coverage
          pypkgs.mypy
          pypkgs.pytest
          pypkgs.pytest-asyncio
          pypkgs.pytestCheckHook
          pypkgs.types-psutil
          pypkgs.twine
          pkgs.ruff
        ];
        mkApp = python: python.pkgs.buildPythonPackage {
          pname = pyprojectToml.tool.poetry.name;
          pyproject = true;
          version = pyprojectToml.tool.poetry.version;
          src = ./.;
          nativeBuildInputs = [ python.pkgs.poetry-core ];
          propagatedBuildInputs = [
            python.pkgs.humanize
            python.pkgs.psutil
            python.pkgs.wrapt
          ];
          nativeCheckInputs = nativeCheckInputs python.pkgs;
          pythonImportsCheck = [ "charmonium.time_block" ];
        };
      in rec {
        packages = rec {
          py311 = mkApp pkgs.python311;
          py312 = mkApp pkgs.python312;
          py313 = mkApp pkgs.python313;
          py314 = mkApp pkgs.python314;
        };
        devShells = {
          default = pkgs.mkShell {
            packages = [
              (pkgs.python313.withPackages (
                pypkgs: builtins.filter
                  isPythonPackage
                  (packages.py313.nativeBuildInputs ++ packages.py313.propagatedBuildInputs ++ (nativeCheckInputs pypkgs))
              ))
            ];
          };
        };
      }
    );
}
