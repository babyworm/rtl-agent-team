# sat_add reference model — worked example for scripts/run_ref_model.py.
# run_ref_model.py invokes the default target with cwd set to this directory,
# then auto-detects the executable under build/.

CC      ?= cc
CFLAGS  ?= -std=c11 -O2 -Wall -Wextra -Werror

all: build/sat_add_ref

build/sat_add_ref: sat_add_ref.c include/sat_add_ref.h
	@mkdir -p build
	@$(CC) $(CFLAGS) -Iinclude -o $@ sat_add_ref.c

clean:
	rm -rf build

.PHONY: all clean
