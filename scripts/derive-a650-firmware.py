#!/usr/bin/env python3
"""Derive the A650 GMU startup inputs AdrenoFirmware's AdrenoA650.c consumes from the pinned Linux sources and the stock kona
device tree of the phone: the GPU performance levels and their RPMh corners (qcom,gpu-pwrlevels and gpu_opp_table), the GMU
level (a6xx_gmu_resume's 200 MHz core clock), the fixed a650 bandwidth table (a6xx_hfi.c a650_build_bw_table), the zap
peripheral (GPU_PAS_ID, qcom,kgsl-hyp, pil_gpu_mem), the command database reservation and the chip id. Writes
kits/AdrenoFirmware/AdrenoA650Source.h (or --output PATH); --check compares instead.

The GMU's CX corner is not in either pinned source: Linux takes it from a mainline GMU OPP table this phone's stock tree does
not carry, and the vendor kgsl hardcodes RPMH_REGULATOR_LEVEL_MIN_SVS in kgsl_gmu.c rpmh_gmu_arc_votes_init. --gmu-level
takes that number (48 for MIN_SVS, dt-bindings/regulator/qcom,rpmh-regulator.h) and the header records where it came from."""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '.cache/adreno-source/drivers/gpu/drm/msm'
OUT = ROOT / 'kits/AdrenoFirmware/AdrenoA650Source.h'

def argument(name, default=None):
    if name in sys.argv[1:]:
        return sys.argv[sys.argv.index(name) + 1]
    if default is None:
        raise SystemExit(name + ' is required')
    return default

def literal(text, pattern, what):
    found = re.findall(pattern, text)
    if len(found) != 1:
        raise SystemExit('expected one ' + what + ', found ' + str(len(found)))
    return found[0]

def node(dts, label):
    """the body of the first node with this label"""
    start = dts.index(label + ': ')
    body_start = dts.index('{', start) + 1
    depth, at = 1, body_start
    while depth:
        if dts[at] == '{':
            depth += 1
        elif dts[at] == '}':
            depth -= 1
        at += 1
    return dts[body_start:at - 1]

def cells(text, name):
    return [int(v, 0) for v in re.search(r'\b' + re.escape(name) + r' = <([^>]+)>;', text).group(1).split()]

def main():
    dts = Path(argument('--dts')).read_text()
    gmu_level = int(argument('--gmu-level'), 0)
    hfi_c = (SRC / 'adreno/a6xx_hfi.c').read_text()
    gmu_c = (SRC / 'adreno/a6xx_gmu.c').read_text()
    gpu_c = (SRC / 'adreno/a6xx_gpu.c').read_text()
    # GPU levels: qcom,gpu-pwrlevels gives the frequencies kgsl runs, gpu_opp_table their RPMh corners (opp-microvolt holds
    # the corner number on this tree, as kgsl's rpmh_arc_votes_init reads it through dev_pm_opp_get_voltage)
    gpu = node(dts, 'msm_gpu')
    levels = re.findall(r'qcom,gpu-pwrlevel@(\d+) \{\s*reg = <0x[0-9a-f]+>;\s*qcom,gpu-freq = <(0x[0-9a-f]+)>;', gpu)
    freqs = sorted({int(f, 16) for _, f in levels if int(f, 16)})
    if len(levels) < 2 or len(freqs) + 1 != len(levels):
        raise SystemExit('unexpected qcom,gpu-pwrlevels')
    opp = node(dts, 'gpu_opp_table')
    corners = {}
    for hz_hi, hz_lo, level in re.findall(r'opp-hz = <(0x[0-9a-f]+) (0x[0-9a-f]+)>;\s*opp-microvolt = <(0x[0-9a-f]+)>;', opp):
        corners[(int(hz_hi, 16) << 32) | int(hz_lo, 16)] = int(level, 16)
    if sorted(corners) != freqs:
        raise SystemExit('gpu_opp_table does not cover qcom,gpu-pwrlevels')
    for i in range(1, len(freqs)):
        if corners[freqs[i]] <= corners[freqs[i - 1]]:
            raise SystemExit('gpu corners are not ascending')
    chip_id = cells(gpu, 'qcom,chipid')[0]
    hbb = cells(gpu, 'qcom,highest-bank-bit')[0]
    mal = cells(gpu, 'qcom,min-access-length')[0]
    ubwc = cells(gpu, 'qcom,ubwc-mode')[0]
    # the GMU runs at 200 MHz for the boot (a6xx_gmu_resume), the only non-zero GMU level the perf table carries
    gmu_hz = int(literal(gmu_c, r'clk_set_rate\(gmu->core_clk, (\d+)\);', 'gmu core clock'))
    # a650_build_bw_table, value for value
    bw = hfi_c[hfi_c.index('static void a650_build_bw_table('):hfi_c.index('static void a690_build_bw_table(')]
    bw_levels = int(literal(bw, r'msg->bw_level_num = (\d+);', 'bw levels'))
    ddr_num = int(literal(bw, r'msg->ddr_cmds_num = (\d+);', 'ddr num'))
    ddr_wait = int(literal(bw, r'msg->ddr_wait_bitmask = (0x[0-9a-f]+);', 'ddr wait'), 16)
    ddr_addrs = [int(v, 16) for _, v in sorted(re.findall(r'msg->ddr_cmds_addrs\[(\d)\] = (0x[0-9a-f]+);', bw))]
    ddr_data = [int(v, 16) for _, v in sorted(re.findall(r'msg->ddr_cmds_data\[0\]\[(\d)\] =\s+(0x[0-9a-f]+);', bw))]
    cnoc_num = int(literal(bw, r'msg->cnoc_cmds_num = (\d+);', 'cnoc num'))
    cnoc_wait = int(literal(bw, r'msg->cnoc_wait_bitmask = (0x[0-9a-f]+);', 'cnoc wait'), 16)
    cnoc_addr = int(literal(bw, r'msg->cnoc_cmds_addrs\[0\] = (0x[0-9a-f]+);', 'cnoc addr'), 16)
    cnoc_data = [int(v, 16) for _, v in sorted(re.findall(r'msg->cnoc_cmds_data\[(\d)\]\[0\] =\s+(0x[0-9a-f]+);', bw))]
    if bw_levels != 1 or ddr_num != len(ddr_addrs) or ddr_num != len(ddr_data) or cnoc_num != 1 or len(cnoc_data) != 2:
        raise SystemExit('a650_build_bw_table changed shape')
    pas_id = int(literal(gpu_c, r'#define GPU_PAS_ID (\d+)\n', 'pas id'))
    pil = node(dts, 'pil_gpu')
    if cells(pil, 'qcom,pas-id')[0] != pas_id or '"a650_zap"' not in pil:
        raise SystemExit('the device tree zap peripheral differs from GPU_PAS_ID / a650_zap')
    region = cells(node(dts, 'pil_gpu_mem'), 'reg')
    db = cells(node(dts, 'cmd_db'), 'reg')
    if len(region) != 4 or len(db) != 4:
        raise SystemExit('reserved memory cells changed')
    lines = ['/* SPDX-License-Identifier: BSD-2-Clause-Patent */',
             '#ifndef ADRENO_A650_SOURCE_H', '#define ADRENO_A650_SOURCE_H', '#include <stdint.h>',
             '/* Generated by scripts/derive-a650-firmware.py from the pinned a6xx_hfi.c (a650_build_bw_table), a6xx_gmu.c',
             ' * (a6xx_gmu_resume), a6xx_gpu.c (GPU_PAS_ID) and the stock kona device tree of the Xperia 1 II (qcom,kgsl-3d0,',
             ' * qcom,gpu-pwrlevels, gpu_opp_table, qcom,kgsl-hyp, pil_gpu_mem, cmd_db). Do not edit by hand. */',
             '#define ADRENO_A650_CHIP_ID 0x%08x' % chip_id,
             '#define ADRENO_A650_HIGHEST_BANK_BIT %d' % hbb,
             '#define ADRENO_A650_MIN_ACCESS_LENGTH %d' % mal,
             '#define ADRENO_A650_UBWC_MODE %d' % ubwc,
             '/* off, then qcom,gpu-pwrlevels ascending, each with the RPMh corner gpu_opp_table gives it */',
             '#define ADRENO_A650_GPU_LEVELS %d' % (len(freqs) + 1),
             'typedef struct {uint64_t hz;uint32_t level;} AdrenoA650Level;',
             'static const AdrenoA650Level adreno_a650_gpu_levels[%d]={{0,0},%s};' % (len(freqs) + 1, ','.join('{%d,%d}' % (f, corners[f]) for f in freqs)),
             '/* the GMU boot clock of a6xx_gmu_resume; the corner is the vendor kgsl_gmu.c rpmh_gmu_arc_votes_init value (--gmu-level) */',
             '#define ADRENO_A650_GMU_LEVELS 2',
             'static const AdrenoA650Level adreno_a650_gmu_levels[2]={{0,0},{%d,%d}};' % (gmu_hz, gmu_level),
             '/* a650_build_bw_table: one "off" level, the fixed CN0 and DDR command sets */',
             '#define ADRENO_A650_BW_LEVELS %d' % bw_levels,
             '#define ADRENO_A650_DDR_COMMANDS %d' % ddr_num,
             '#define ADRENO_A650_DDR_WAIT_MASK 0x%x' % ddr_wait,
             'static const uint32_t adreno_a650_ddr_addresses[%d]={%s};' % (ddr_num, ','.join('0x%x' % v for v in ddr_addrs)),
             'static const uint32_t adreno_a650_ddr_data[%d]={%s};' % (ddr_num, ','.join('0x%08x' % v for v in ddr_data)),
             '#define ADRENO_A650_CNOC_COMMANDS %d' % cnoc_num,
             '#define ADRENO_A650_CNOC_WAIT_MASK 0x%x' % cnoc_wait,
             '#define ADRENO_A650_CNOC_ADDRESS 0x%x' % cnoc_addr,
             'static const uint32_t adreno_a650_cnoc_data[2]={%s};' % ','.join('0x%08x' % v for v in cnoc_data),
             '/* the zap shader peripheral and its carveout, the AOP command database */',
             '#define ADRENO_A650_ZAP_PAS_ID %d' % pas_id,
             '#define ADRENO_A650_ZAP_REGION_BASE UINT64_C(0x%x)' % ((region[0] << 32) | region[1]),
             '#define ADRENO_A650_ZAP_REGION_BYTES UINT64_C(0x%x)' % ((region[2] << 32) | region[3]),
             '#define ADRENO_A650_COMMAND_DB_BASE UINT64_C(0x%x)' % ((db[0] << 32) | db[1]),
             '#define ADRENO_A650_COMMAND_DB_BYTES UINT64_C(0x%x)' % ((db[2] << 32) | db[3]),
             '#endif']
    text = '\n'.join(lines) + '\n'
    out = Path(argument('--output', str(OUT)))
    if '--check' in sys.argv[1:]:
        if out.read_text() != text:
            raise SystemExit('AdrenoA650Source.h is stale')
        print('PASS: A650 firmware inputs match the pinned sources and the device tree')
        return
    out.write_text(text)
    print('PASS: %d GPU levels, %d GMU levels, %d DDR commands' % (len(freqs) + 1, 2, ddr_num))

main()
