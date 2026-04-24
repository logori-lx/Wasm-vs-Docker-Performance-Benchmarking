# ==========================================
# 变量定义 (Variables)
# ==========================================
WORK_DIR = bench
REPORTS_DIR = reports

# CLI (RSA) 相关变量
CLI_DOCKER_IMAGE = rsa_bench_docker
CLI_SRC_DIR = src/rsa_generate
CLI_WASM_TARGET = ${CLI_SRC_DIR}/rsa_bench/target/wasm32-wasip1/release/rsa_bench.wasm
CLI_AOT_TARGET = ${CLI_SRC_DIR}/rsa_bench/target/wasm32-wasip1/release/rsa_bench_aot.wasm
CLI_WASM_OUTPUT = rsa_bench_aot.wasm

# WEB 相关变量
WEB_DOCKER_IMAGE = web_bench_docker
WEB_SRC_DIR = src/web_service
WEB_WASM_TARGET = ${WEB_SRC_DIR}/web_bench/target/wasm32-wasip1/release/web_bench.wasm
WEB_WASM_OUTPUT = web_bench.wasm

# Processing Rate 变量
PR_DOCKER_IMAGE = processing_rate_bench_docker
PR_SRC_DIR = src/processing_rate_bench
PR_WASM_TARGET = ${PR_SRC_DIR}/target/wasm32-wasip1/release/processing_rate_bench.wasm
PR_WASM_OUTPUT = processing_rate_bench.wasm


.PHONY: all build-all build-cli build-web build-processing-rate copy init-remote bench-remote-cli bench-remote-web bench-remote-processing-rate bench-remote-all clean

# 默认构建并准备好所有产物
all: build-all copy

build-all: build-cli build-web build-processing-rate

# --- 1. 构建任务 (Build) ---

build-cli:
	@echo "=> Building CLI Docker image..."
	cd src/rsa_generate/ && docker build -t $(CLI_DOCKER_IMAGE) .
	docker save $(CLI_DOCKER_IMAGE) -o $(CLI_DOCKER_IMAGE).tar
	@echo "=> Compiling CLI Rust to WASM..."
	cd src/rsa_generate/rsa_bench && cargo build --target wasm32-wasip1 --release
	@echo "=> AOT compiling CLI WASM with WasmEdge..."
	wasmedge compile $(CLI_WASM_TARGET) $(CLI_AOT_TARGET)

build-web:
	@echo "=> Building WEB Docker image..."
	cd src/web_service/ && docker build -t $(WEB_DOCKER_IMAGE) .
	docker save $(WEB_DOCKER_IMAGE) -o $(WEB_DOCKER_IMAGE).tar
	@echo "=> Compiling WEB Rust to WASM..."
	cd src/web_service/web_bench && cargo build --target wasm32-wasip1 --release

build-processing-rate:
	@echo "=> Building Processing Rate Docker image..."
	cd $(PR_SRC_DIR) && docker build -t $(PR_DOCKER_IMAGE) .
	docker save $(PR_DOCKER_IMAGE) -o $(PR_DOCKER_IMAGE).tar
	@echo "=> Compiling Processing Rate Rust to WASM..."
	cd $(PR_SRC_DIR) && cargo build --target wasm32-wasip1 --release

# --- 2. 产物整理任务 (Copy) ---
copy: build-all
	@echo "=> Preparing $(WORK_DIR) directory..."
	@if [ ! -d "$(WORK_DIR)" ]; then mkdir $(WORK_DIR); fi

	# copy cli test related files
	cp src/rsa_generate/bench.py $(WORK_DIR)/bench.py
	cp $(CLI_DOCKER_IMAGE).tar $(WORK_DIR)/
	cp $(CLI_AOT_TARGET) $(WORK_DIR)/$(CLI_WASM_OUTPUT)

	# copy web test related files
	cp src/web_service/bench.py $(WORK_DIR)/web_bench.py
	cp $(WEB_DOCKER_IMAGE).tar $(WORK_DIR)/
	cp $(WEB_WASM_TARGET) $(WORK_DIR)/

	cp $(PR_SRC_DIR)/bench.py $(WORK_DIR)/processing_rate_bench.py
	cp $(PR_DOCKER_IMAGE).tar $(WORK_DIR)/
	cp $(PR_WASM_TARGET) $(WORK_DIR)/

# --- 3. Ansible 远程执行任务 (Remote Execute) ---
init-remote:
	@echo "=> Preparing $(WORK_DIR) directory..."
	@if [ ! -d "$(WORK_DIR)" ]; then mkdir $(WORK_DIR); fi
	# copy init script for cloud machines
	cp init_remote.bash $(WORK_DIR)/init_remote.bash
	@echo "=> Initializing remote environments..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "init"

bench-remote-cli: copy
	@echo "=> Running CLI benchmarks on remote..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "bench_cli"

bench-remote-web: copy
	@echo "=> Running WEB benchmarks on remote..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "bench_web"

bench-remote-processing-rate: copy
	@echo "=> Running Processing Rate benchmarks on remote..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "bench_processing_rate"

bench-remote-all: copy
	@echo "=> Running ALL benchmarks on remote..."
	cd playbook && ansible-playbook -i hosts run_and_fetch.yml --tags "bench_cli,bench_web,bench_processing_rate"

# --- 本地运行 ---
bench-local-cli: build-cli
	@echo "=> Running CLI benchmarks locally..."
	cp $(CLI_AOT_TARGET) $(CLI_SRC_DIR)/${CLI_WASM_OUTPUT}
	cd $(CLI_SRC_DIR) && python bench.py
	rm -f $(CLI_SRC_DIR)/${CLI_WASM_OUTPUT}

bench-local-web: build-web
	@echo "=> Running WEB benchmarks locally..."
	cp $(WEB_WASM_TARGET) $(WEB_SRC_DIR)/${WEB_WASM_OUTPUT}
	cd $(WEB_SRC_DIR) && python bench.py
	rm -f $(WEB_SRC_DIR)/${WEB_WASM_OUTPUT}

bench-local-processing-rate: build-processing-rate
	@echo "=> Running Processing Rate benchmarks locally..."
	cp $(PR_WASM_TARGET) $(PR_SRC_DIR)/${PR_WASM_OUTPUT}
	cd $(PR_SRC_DIR) && python bench.py
	rm -f $(PR_SRC_DIR)/${PR_WASM_OUTPUT}

bench-local-all: bench-local-cli bench-local-web bench-local-processing-rate

# --- 帮助文档 ---
help:
	@echo "=========================================="
	@echo "  Benchmark Toolchain - Available Commands"
	@echo "=========================================="
	@echo ""
	@echo "BUILD & PREPARE:"
	@echo "  make build-all"
	@echo "  make build-cli"
	@echo "  make build-web"
	@echo "  make build-processing-rate"
	@echo ""
	@echo "LOCAL BENCHMARKS:"
	@echo "  make bench-local-cli"
	@echo "  make bench-local-web"
	@echo "  make bench-local-processing-rate"
	@echo "  make bench-local-all"
	@echo ""
	@echo "REMOTE BENCHMARKS:"
	@echo "  make init-remote"
	@echo "  make bench-remote-cli"
	@echo "  make bench-remote-web"
	@echo "  make bench-remote-processing-rate"
	@echo "  make bench-remote-all"
	@echo ""
	@echo "CLEAN:"
	@echo "  make clean"
	@echo ""

# --- 清理 ---
clean:
	@echo "=> Cleaning up..."
	cd src/web_service/web_bench && cargo clean
	cd src/rsa_generate/rsa_bench && cargo clean
	cd $(PR_SRC_DIR) && cargo clean

	rm -rf $(WORK_DIR)
	rm -rf *.csv *.tar
	rm -rf $(REPORTS_DIR)/*.txt

	rm -f $(CLI_WASM_OUTPUT) $(WEB_WASM_OUTPUT) $(PR_WASM_OUTPUT)
	rm -f $(CLI_DOCKER_IMAGE).tar $(WEB_DOCKER_IMAGE).tar $(PR_DOCKER_IMAGE).tar

	docker rmi $(CLI_DOCKER_IMAGE) $(WEB_DOCKER_IMAGE) $(PR_DOCKER_IMAGE) || true

	rm -f $(WEB_SRC_DIR)/${WEB_WASM_OUTPUT} $(WEB_SRC_DIR)/*.csv
	rm -f $(CLI_SRC_DIR)/${CLI_WASM_OUTPUT} $(CLI_SRC_DIR)/*.csv
	rm -f $(PR_SRC_DIR)/${PR_WASM_OUTPUT} $(PR_SRC_DIR)/*.csv
