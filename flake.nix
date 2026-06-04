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
        pyprojectToml = builtins.fromTOML (builtins.readFile ./pyproject.toml);
        mkApp = python: python.pkgs.buildPythonPackage {
          pname = pyprojectToml.tool.poetry.name;
          pyproject = true;
          version = pyprojectToml.tool.poetry.version;
          src = ./.;
          nativeBuildInputs = [ python.pkgs.poetry-core ];
          propagatedBuildInputs = [ ];
          checkInputs = [
            python.pkgs.mypy
            python.pkgs.pytest
            python.pkgs.autoflake
            python.pkgs.isort
            python.pkgs.black
            python.pkgs.pylint
            python.pkgs.coverage
            python.pkgs.types-psutil
            python.pkgs.pytest-asyncio
          ];
          pythonImportsCheck = [ "charmonium.time_block" ];
          nativeCheckInputs = [ python.pkgs.pytestCheckHook ];
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
              pkgs.ruff
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
