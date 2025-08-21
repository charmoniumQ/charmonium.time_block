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
        python = pkgs.python313;
        pyprojectToml = builtins.fromTOML (builtins.readFile ./pyproject.toml);
        checkInputsPy = pypkgs: [
          pypkgs.bump2version
          pypkgs.mypy
          pypkgs.pytest
          pypkgs.tox
          pypkgs.autoflake
          pypkgs.isort
          pypkgs.black
          pypkgs.pylint
          pypkgs.coverage
          pypkgs.types-psutil
          pypkgs.pytest-asyncio
          pypkgs.twine
        ];
      in rec {
        packages = rec {
          default = charmonium-time-block;
          charmonium-time-block = python.pkgs.buildPythonPackage {
            pname = pyprojectToml.tool.poetry.name;
            pyproject = true;
            version = pyprojectToml.tool.poetry.version;
            src = ./.;
            nativeBuildInputs = [ python.pkgs.poetry-core ];
            propagatedBuildInputs = [ ];
            checkInputs = (checkInputsPy python.pkgs) ++ [ pkgs.bash ];
            pythonImportsCheck = [ "charmonium.time_block" ];
            nativeCheckInputs = [ python.pkgs.pytestCheckHook ];
          };
        };
        devShells = {
          default = pkgs.mkShell {
            packages = [
              (python.withPackages checkInputsPy)
              pkgs.poetry
            ];
          };
        };
      }
    );
}
