# Reference Model Build Makefile
# Builds C reference model as standalone executable and DPI-C shared library
#
# Targets:
#   make          — build standalone ref model
#   make dpi      — build DPI-C .so for SV co-simulation
#   make test     — run self-test with test vectors
#   make clean    — remove build artifacts

CC      = gcc
CFLAGS  = -std=c11 -O2 -Wall -Wextra -Wpedantic
LDFLAGS =

# DPI-C shared library flags
DPI_CFLAGS = -fPIC -shared -DDPI_MODE
DPI_TARGET = build/lib{{MODULE_NAME}}_dpi.so

# Source files
SRCS    = src/{{MODULE_NAME}}_ref.c
MAIN_SRC = src/{{MODULE_NAME}}_main.c
HEADERS = include/{{MODULE_NAME}}_ref.h include/dpi_wrapper.h
DPI_SRC = src/{{MODULE_NAME}}_dpi_wrapper.c

# Standalone executable
TARGET  = build/{{MODULE_NAME}}_ref

.PHONY: all dpi test clean

all: $(TARGET)

$(TARGET): $(SRCS) $(HEADERS)
	@mkdir -p build
	$(CC) $(CFLAGS) $(LDFLAGS) -Iinclude -o $@ $(SRCS) $(MAIN_SRC)

dpi: $(DPI_TARGET)

$(DPI_TARGET): $(SRCS) $(DPI_SRC) $(HEADERS)
	@mkdir -p build
	$(CC) $(CFLAGS) $(DPI_CFLAGS) -Iinclude -o $@ $(SRCS) $(DPI_SRC)

test: $(TARGET)
	@echo "=== Running self-test ==="
	./$(TARGET) --self-test
	@echo "=== Self-test complete ==="

clean:
	rm -rf build/
