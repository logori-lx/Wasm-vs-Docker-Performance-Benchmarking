# ==========================================
# 变量定义 (Variables)
# ==========================================
WORK_DIR = bench

# CLI (RSA) 相关变量
CLI_DOCKER_IMAGE = rsa_bench_docker
CLI_SRC_DIR = src/rsa_generate
CLI_WASM_TARGET = ${CLI_SRC_DIR}/rsa_bench/target/wasm32-wasip1/release/rsa_bench.wasm
CLI_WASM_OUTPUT = rsa_bench.wasm

# WEB 相关变量
WEB_DOCKER_IMAGE = web_bench_docker
WEB_SRC_DIR = src/web_service
WEB_WASM_TARGET = ${WEB_SRC_DIR}/web_bench/target/wasm32-wasip1/release/web_bench.wasm
WEB_WASM_OUTPUT = web_bench.wasm

REPORTS_DIR = reports

.PHONY: all build-all build-cli build-web copy init-remote bench-remote-cli bench-remote-web bench-remote-all clean

# 默认构建并准备好所有产物
all: build-all copy

build-all: build-cli build-web

# --- 1. 构建任务 (Build) ---

build-cli:
	@echo "=> Building CLI Docker image..."
	cd src/rsa_generate/ && docker build -t $(CLI_DOCKER_IMAGE) .
	docker save $(CLI_DOCKER_IMAGE) -o $(CLI_DOCKER_IMAGE).tar
	@echo "=> Compiling CLI Rust to WASM..."
	cd src/rsa_generate/rsa_bench && cargo build --target wasm32-wasip1 --release

build-web:
	@echo "=> Building WEB Docker image..."
	cd src/web_service/ && docker build -t $(WEB_DOCKER_IMAGE) .
	docker save $(WEB_DOCKER_IMAGE) -o $(WEB_DOCKER_IMAGE).tar
	@echo "=> Compiling WEB Rust to WASM..."
	cd src/web_service/web_bench && cargo build --target wasm32-wasip1 --release

# --- 2. 产物整理任务 (Copy) ---

copy: build-all
	@echo "=> Preparing $(WORK_DIR) directory..."
	@if [ ! -d "$(WORK_DIR)" ]; then mkdir $(WORK_DIR); fi
	
	# copy init script for cloud machines
	cp init_remote.bash $(WORK_DIR)/init_remote.bash
	
	# copy cli test related files
	cp src/rsa_generate/bench.py $(WORK_DIR)/bench.py
	cp $(CLI_DOCKER_IMAGE).tar $(WORK_DIR)/
	cp $(CLI_WASM_TARGET) $(WORK_DIR)/
	
	# copy web test related files (here automatically rename bench.py to web_bench.py to match the Playbook)
	cp src/web_service/bench.py $(WORK_DIR)/web_bench.py
	cp $(WEB_DOCKER_IMAGE).tar $(WORK_DIR)/
	cp $(WEB_WASM_TARGET) $(WORK_DIR)/

# --- 3. Ansible 远程执行任务 (Remote Execute) ---

init-remote:
	@echo "=> Initializing remote environments..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "init"

bench-remote-cli: copy 
	@echo "=> Running CLI benchmarks on remote..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "bench_cli"

bench-remote-web: copy
	@echo "=> Running WEB benchmarks on remote..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "bench_web"

bench-remote-all: copy
	@echo "=> Running ALL benchmarks on remote..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "bench_cli,bench_web"


bench-local-cli: build-cli
	@echo "=> Running CLI benchmarks locally..."
	cp $(CLI_WASM_TARGET) $(CLI_SRC_DIR)/${CLI_WASM_OUTPUT}
	cd $(CLI_SRC_DIR) && python bench.py
	rm -f $(CLI_SRC_DIR)/${CLI_WASM_OUTPUT}

bench-local-web: build-web
	@echo "=> Running WEB benchmarks locally..."
	cp $(WEB_WASM_TARGET) $(WEB_SRC_DIR)/${WEB_WASM_OUTPUT}
	cd $(WEB_SRC_DIR) && python bench.py
	rm -f $(WEB_SRC_DIR)/${WEB_WASM_OUTPUT}

bench-local-all: bench-local-web bench-local-cli


# --- 5. 帮助任务 (Help) ---
help:
	@echo "=========================================="
	@echo "  Benchmark Toolchain - Available Commands"
	@echo "=========================================="
	@echo ""
	@echo "BUILD & PREPARE:"
	@echo "  make build-all          - Build both CLI and WEB Docker images + WASM binaries"
	@echo "  make build-cli          - Build CLI (RSA) Docker image and WASM only"
	@echo "  make build-web          - Build WEB service Docker image and WASM only"
	@echo "  make copy               - Copy all artifacts to $(WORK_DIR)/ directory"
	@echo "  make all                - Build everything and copy artifacts (default)"
	@echo ""
	@echo "LOCAL BENCHMARKS:"
	@echo "  make bench-local-cli    - Run CLI (RSA) benchmarks on local machine"
	@echo "  make bench-local-web    - Run WEB service benchmarks on local machine"
	@echo "  make bench-local-all    - Run both CLI and WEB benchmarks locally"
	@echo ""
	@echo "REMOTE BENCHMARKS (via Ansible):"
	@echo "  make init-remote        - Initialize remote environments (Ansible)"
	@echo "  make bench-remote-cli   - Run CLI benchmarks on remote machines"
	@echo "  make bench-remote-web   - Run WEB benchmarks on remote machines"
	@echo "  make bench-remote-all   - Run ALL benchmarks on remote machines"
	@echo ""
	@echo "CLEANUP:"
	@echo "  make clean              - Remove all generated artifacts, containers, and reports"
	@echo ""
# --- 4. 清理任务 (Clean) ---
clean:
	@echo "=> Cleaning up generated artifacts..."
	cd src/web_service/web_bench && cargo clean
	cd src/rsa_generate/rsa_bench && cargo clean
	rm -rf $(WORK_DIR) 
	rm -rf *.csv *.tar
	rm -rf $(REPORTS_DIR)/*
	rm -f $(CLI_WASM_OUTPUT) $(WEB_WASM_OUTPUT)
	rm -f $(CLI_DOCKER_IMAGE).tar $(WEB_DOCKER_IMAGE).tar
	docker rmi $(CLI_DOCKER_IMAGE) $(WEB_DOCKER_IMAGE) || true

	rm -f $(WEB_SRC_DIR)/${WEB_WASM_OUTPUT}
	rm -f $(WEB_SRC_DIR)/*.csv
	rm -f $(CLI_SRC_DIR)/${CLI_WASM_OUTPUT}
	rm -f $(CLI_SRC_DIR)/*.csv
