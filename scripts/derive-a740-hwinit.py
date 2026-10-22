#!/usr/bin/env python3
"""Derive the A740 hw_init register table (a6xx_gpu.c hw_init, a6xx_set_hwcg, a6xx_set_cp_protect) from pinned sources.

Offsets come from the pinned XMLs with exact A7XX variant selection (a6xx.xml first, then adreno_common.xml); the hwcg and
protect values from the pinned a6xx_catalog.c (a740_hwcg, a730_protect); the scalar values hw_init writes on the a740 branches
from the pinned a6xx_gpu.c, a6xx_gmu.c and the catalog entry itself. Writes drivers/NativeAdreno/NativeAdrenoA740HwInit.h (or
--output PATH); --check compares instead."""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '.cache/adreno-source/drivers/gpu/drm/msm'
XML = SRC / 'registers/adreno'
ORDER = ['A2XX', 'A3XX', 'A4XX', 'A5XX', 'A6XX', 'A7XX', 'A8XX']
OUT = ROOT / 'drivers/NativeAdreno/NativeAdrenoA740HwInit.h'

def matches(variants):
    if variants is None:
        return True
    for part in variants.split(','):
        part = part.strip()
        if '-' in part:
            left, right = part.split('-', 1)
            low = ORDER.index(left) if left else 0
            high = ORDER.index(right) if right else len(ORDER) - 1
            if low <= ORDER.index('A7XX') <= high:
                return True
        elif part == 'A7XX':
            return True
    return False

def resolve(name, files, kind='reg(?:32|64)'):
    for f in files:
        text = (XML / f).read_text()
        hits = set()
        for m in re.finditer(r'<(' + kind + r') offset="(0x[0-9a-fA-F]+)" name="' + name + r'"([^>]*)>', text):
            v = re.search(r'variants="([^"]+)"', m.group(3))
            if matches(v.group(1) if v else None):
                hits.add(int(m.group(2), 16))
        if len(hits) > 1:
            raise SystemExit('ambiguous ' + name + ' in ' + f)
        if hits:
            return hits.pop()
    raise SystemExit('missing ' + name)

def bits(file, bitset, names):
    """bit positions of the named fields of a bitset, or of a reg32 with inline bitfields, A7XX variants only"""
    text = (XML / file).read_text()
    positions = {}
    for m in re.finditer(r'<(?:bitset name="' + bitset + r'"|reg32 offset="0x[0-9a-fA-F]+" name="' + bitset + r'")([^>]*)>', text):
        v = re.search(r'variants="([^"]+)"', m.group(1))
        if not matches(v.group(1) if v else None):
            continue
        body = text[m.end():text.index('</', m.end())]
        for field in re.finditer(r'<bitfield (?:name="(\w+)" pos="(\d+)"|pos="(\d+)" name="(\w+)")[^>]*?(?: variants="([^"]+)")?/>', body):
            name = field.group(1) or field.group(4)
            pos = int(field.group(2) or field.group(3))
            if matches(field.group(5)):
                positions[name] = pos
    missing = [n for n in names if n not in positions]
    if missing:
        raise SystemExit('bitset ' + bitset + ' lacks ' + repr(missing))
    return sum(1 << positions[n] for n in names)

def literal(text, pattern, what):
    """exactly one match of a source line pattern; the first group is the number"""
    found = re.findall(pattern, text)
    if len(found) != 1:
        raise SystemExit('expected one ' + what + ' in the pinned source, found ' + str(len(found)))
    return int(found[0], 0)

GPU = ['GBIF_HALT', 'RBBM_GBIF_HALT', 'RBBM_SECVID_TSB_CNTL', 'RBBM_SECVID_TSB_TRUSTED_BASE',
       'RBBM_SECVID_TSB_TRUSTED_SIZE', 'RBBM_GBIF_CLIENT_QOS_CNTL', 'UCHE_GBIF_GX_CONFIG',
       'RBBM_PERFCTR_GPU_BUSY_MASKED', 'UCHE_TRAP_BASE', 'UCHE_WRITE_THRU_BASE', 'UCHE_GMEM_RANGE_MIN',
       'UCHE_GMEM_RANGE_MAX', 'UCHE_CACHE_WAYS', 'CP_AHB_CNTL', 'RBBM_PERFCTR_CNTL', 'RBBM_INTERFACE_HANG_INT_CNTL',
       'UCHE_CLIENT_PF', 'CP_PROTECT_CNTL', 'UCHE_CMDQ_CONFIG', 'CP_APRIV_CNTL', 'CP_BV_APRIV_CNTL',
       'CP_LPAC_APRIV_CNTL', 'RB_CMP_DBG_ECO_CNTL', 'RBBM_INT_0_MASK', 'CP_SQE_INSTR_BASE', 'CP_RB_BASE',
       'CP_RB_CNTL', 'CP_RB_RPTR_ADDR', 'CP_BV_RB_RPTR_ADDR', 'CP_SQE_CNTL', 'CP_RB_RPTR', 'CP_RB_WPTR',
       'RBBM_STATUS', 'RBBM_INT_0_STATUS', 'CP_HW_FAULT', 'CP_INTERRUPT_STATUS', 'RBBM_CLOCK_CNTL',
       'RBBM_SECVID_TRUST_CNTL', 'RBBM_STATUS3', 'CP_SQE_STAT_ADDR', 'CP_SQE_STAT_DATA',
       'RB_NC_MODE_CNTL', 'TPL1_NC_MODE_CNTL', 'SP_NC_MODE_CNTL', 'CP_APERTURE_CNTL_HOST', 'GRAS_NC_MODE_CNTL',
       'UCHE_MODE_CNTL', 'RBBM_NC_MODE_CNTL', 'RBBM_INT_CLEAR_CMD', 'CP_ALWAYS_ON_COUNTER']
GMU = ['GPU_GMU_AO_GMU_CGC_MODE_CNTL', 'GPU_GMU_AO_GMU_CGC_DELAY_CNTL', 'GPU_GMU_AO_GMU_CGC_HYST_CNTL']
# names of A7XX_INT_MASK in the pinned a6xx_gpu.c, in its order
INT_MASK = ['CP_AHB_ERROR', 'RBBM_ATB_ASYNCFIFO_OVERFLOW', 'RBBM_GPC_ERROR', 'CP_SW', 'CP_HW_ERROR', 'PM4CPINTERRUPT',
            'CP_RB_DONE_TS', 'CP_CACHE_FLUSH_TS', 'RBBM_ATB_BUS_OVERFLOW', 'RBBM_HANG_DETECT', 'UCHE_OOB_ACCESS',
            'UCHE_TRAP_INTR', 'TSBWRITEERROR', 'SWFUSEVIOLATION']
CP_ERRORS = ['CP_OPCODE_ERROR', 'CP_UCODE_ERROR', 'CP_HW_FAULT_ERROR', 'CP_REGISTER_PROTECTION_ERROR',
             'CP_AHB_ERROR', 'CP_VSD_PARITY_ERROR', 'CP_ILLEGAL_INSTR_ERROR',
             'CP_OPCODE_ERROR_LPAC', 'CP_UCODE_ERROR_LPAC', 'CP_HW_FAULT_ERROR_LPAC',
             'CP_REGISTER_PROTECTION_ERROR_LPAC', 'CP_ILLEGAL_INSTR_ERROR_LPAC', 'CP_OPCODE_ERROR_BV',
             'CP_UCODE_ERROR_BV', 'CP_HW_FAULT_ERROR_BV', 'CP_REGISTER_PROTECTION_ERROR_BV', 'CP_ILLEGAL_INSTR_ERROR_BV']
APRIV = ['ICACHE', 'RBFETCH', 'RBPRIVLEVEL', 'RBRPWB']
BR_APRIV = APRIV + ['CDREAD', 'CDWRITE']

def main():
    catalog = (SRC / 'adreno/a6xx_catalog.c').read_text()
    gpu_c = (SRC / 'adreno/a6xx_gpu.c').read_text()
    gmu_c = (SRC / 'adreno/a6xx_gmu.c').read_text()
    defines = [(n, resolve(n, ['a6xx.xml', 'adreno_common.xml'])) for n in GPU]
    defines += [(n, resolve(n, ['a6xx_gmu.xml'])) for n in GMU]
    defines.append(('CP_PROTECT', resolve('CP_PROTECT', ['a6xx.xml'], 'array')))
    block = re.search(r'a740_hwcg\[\]\s*=\s*\{(.*?)\{\},\s*\};', catalog, re.S).group(1)
    hwcg = []
    for name, value in re.findall(r'\{\s*REG_A[67]XX_([A-Z0-9_]+),\s*(0x[0-9a-fA-F]+)\s*\}', block):
        hwcg.append((name, resolve(name, ['a6xx.xml', 'adreno_common.xml']), int(value, 16)))
    if len(hwcg) != block.count('REG_'):
        raise SystemExit('unparsed a740_hwcg entry')
    pblock = re.search(r'a730_protect_regs\[\]\s*=\s*\{(.*?)\};', catalog, re.S).group(1)
    pblock = re.sub(r'/\*.*?\*/', '', pblock, flags=re.S)
    protect = []
    for entry in [e.strip() for e in pblock.split(',\n')]:
        entry = entry.strip().rstrip(',')
        if not entry:
            continue
        if entry == '0':
            protect.append(0)
            continue
        m = re.fullmatch(r'A6XX_PROTECT_(NORDWR|RDONLY)\((0x[0-9a-fA-F]+),\s*(0x[0-9a-fA-F]+)\)', entry)
        if not m:
            raise SystemExit('unparsed protect entry ' + entry)
        reg, length = int(m.group(2), 16), int(m.group(3), 16)
        protect.append(((1 << 31) if m.group(1) == 'NORDWR' else 0) | ((length & 0x3fff) << 18) | (reg & 0x3ffff))
    count_max = int(re.search(r'DECLARE_ADRENO_PROTECT\(a730_protect,\s*(\d+)\)', catalog).group(1))
    # a6xx_set_cp_protect: entries 0..count-2 at their index (zeros skipped), the last one at count_max-1.
    writes = [(i, v) for i, v in enumerate(protect[:-1]) if v] + [(count_max - 1, protect[-1])]
    # the 0x43050a01 catalog entry and the a740 family branches of hw_init, a6xx_set_hwcg and a6xx_gmu_fw_start
    record = re.search(r'\.chip_ids = ADRENO_CHIP_IDS\((0x43050a01)\)([\s\S]*?)\.preempt_record_size', catalog)
    record = record.group(2)
    if '.gmem = 3 * SZ_1M,' not in record or '.hwcg = a740_hwcg' not in record or '.protect = &a730_protect' not in record:
        raise SystemExit('the a740 catalog entry is not the one this script derives from')
    gmem = 3 << 20
    gmu_chipid = int(re.search(r'\.gmu_chipid = (0x[0-9a-f]+)', record).group(1), 16)
    cgc_mode = int(re.search(r'\.gmu_cgc_mode = (0x[0-9a-f]+)', record).group(1), 16)
    mask_text = re.search(r'#define A7XX_INT_MASK \((.*?)\)\n\n', gpu_c, re.S).group(1)
    if re.findall(r'A6XX_RBBM_INT_0_MASK_(\w+)', mask_text) != INT_MASK:
        raise SystemExit('A7XX_INT_MASK fields changed')
    int_mask = bits('a6xx.xml', 'A6XX_RBBM_INT_0_MASK', INT_MASK)
    cp_errors = bits('a6xx.xml', 'A6XX_CP_INT', CP_ERRORS)
    protect_cntl = bits('a6xx.xml', 'a6xx_cp_protect_cntl', ['ACCESS_PROT_EN', 'ACCESS_FAULT_ON_VIOL_EN', 'LAST_SPAN_INF_RANGE'])
    apriv_text = re.search(r'#define A7XX_APRIV_MASK \((.*?)\)\n\n', gpu_c, re.S).group(1)
    if re.findall(r'A6XX_CP_APRIV_CNTL_(\w+)', apriv_text) != APRIV:
        raise SystemExit('A7XX_APRIV_MASK fields changed')
    br_text = re.search(r'#define A7XX_BR_APRIVMASK \((.*?)\)\n\n', gpu_c, re.S).group(1)
    if re.findall(r'A6XX_CP_APRIV_CNTL_(\w+)', br_text) != BR_APRIV[4:] or 'A7XX_APRIV_MASK' not in br_text:
        raise SystemExit('A7XX_BR_APRIVMASK fields changed')
    apriv = bits('a6xx.xml', 'a6xx_cp_apriv_cntl', APRIV)
    br_apriv = bits('a6xx.xml', 'a6xx_cp_apriv_cntl', BR_APRIV)
    pipe_shift = literal((XML / 'a6xx.xml').read_text(), r'<bitfield name="PIPE" low="(\d+)" high="13" type="adreno_pipe"/>', 'aperture pipe field')
    common = (XML / 'adreno_common.xml').read_text()
    pipe_br = literal(common, r'<value value="(\d+)" name="PIPE_BR"/>', 'PIPE_BR')
    pipe_bv = literal(common, r'<value value="(\d+)" name="PIPE_BV"/>', 'PIPE_BV')
    hwcg_fn = gpu_c[gpu_c.index('static void a6xx_set_hwcg('):gpu_c.index('static void a6xx_set_cp_protect(')]
    clock_cntl_on = literal(hwcg_fn, r'else\n\t\tclock_cntl_on = (0x[0-9a-f]+);', 'clock_cntl_on default')
    cgc_delay = literal(hwcg_fn, r'else\n\t\tcgc_delay = (0x[0-9a-f]+);', 'cgc_delay default')
    cgc_hyst = literal(hwcg_fn, r'else\n\t\tcgc_hyst = (0x[0-9a-f]+);', 'cgc_hyst default')
    init_fn = gpu_c[gpu_c.index('static int hw_init('):gpu_c.index('static int a6xx_hw_init(')]
    qos = literal(init_fn, r'else if \(adreno_is_a7xx\(adreno_gpu\)\) \{\n\t\tgpu_write\(gpu, REG_A6XX_RBBM_GBIF_CLIENT_QOS_CNTL, (0x[0-9a-f]+)\);', 'a7xx gbif qos')
    gx_config = literal(init_fn, r'REG_A6XX_UCHE_GBIF_GX_CONFIG, (0x[0-9a-f]+)\);', 'uche gbif gx config')
    trap_base = literal(gpu_c, r'adreno_gpu->uche_trap_base = (0x[0-9a-f]+)ull;', 'uche trap base')
    if 'gmem_range_min = adreno_is_a740_family(adreno_gpu) ? SZ_16M : SZ_1M;' not in init_fn:
        raise SystemExit('a740 gmem base changed')
    gmem_base = 16 << 20
    ways = literal(init_fn, r'if \(adreno_is_a7xx\(adreno_gpu\)\)\n\t\tgpu_write\(gpu, REG_A6XX_UCHE_CACHE_WAYS, BIT\((\d+)\)\);', 'a7xx uche ways')
    ahb = literal(init_fn, r'REG_A6XX_CP_AHB_CNTL, (0x[0-9a-f]+)\);', 'ahb cntl')
    perfctr = literal(init_fn, r'REG_A6XX_RBBM_PERFCTR_CNTL, (0x[0-9a-f]+)\);', 'perfctr cntl')
    hang = literal(init_fn, r'adreno_is_a740_family\(adreno_gpu\)\)\n\t\tgpu_write\(gpu, REG_A6XX_RBBM_INTERFACE_HANG_INT_CNTL, \(1 << 30\) \| (0x[0-9a-f]+)\);', 'a740 hang detect')
    client_pf = re.search(r'REG_A6XX_UCHE_CLIENT_PF, BIT\((\d+)\) \| (0x[0-9a-f]+)\);', init_fn)
    client_pf = (1 << int(client_pf.group(1))) | int(client_pf.group(2), 16)
    cmdq = re.search(r'else if \(adreno_is_a7xx\(adreno_gpu\)\)\n\t\tgpu_write\(gpu, REG_A6XX_UCHE_CMDQ_CONFIG,\n'
                     r'\t\t\t  FIELD_PREP\(GENMASK\(19, 16\), (\d+)\) \|\n\t\t\t  FIELD_PREP\(GENMASK\(15, 12\), (\d+)\) \|\n'
                     r'\t\t\t  FIELD_PREP\(GENMASK\(11, 8\), (\d+)\) \|\n\t\t\t  BIT\((\d+)\) \| BIT\((\d+)\) \|\n'
                     r'\t\t\t  FIELD_PREP\(GENMASK\(1, 0\), (\d+)\)\);', init_fn)
    if not cmdq:
        raise SystemExit('a7xx uche cmdq config changed')
    c = [int(v) for v in cmdq.groups()]
    cmdq = (c[0] << 16) | (c[1] << 12) | (c[2] << 8) | (1 << c[3]) | (1 << c[4]) | c[5]
    rb_cmp = literal(init_fn, r'\} else if \(adreno_is_a7xx\(adreno_gpu\)\) \{\n\t\t/\* Disable non-ubwc read reqs from passing write reqs \*/\n'
                     r'\t\tgpu_rmw\(gpu, REG_A6XX_RB_CMP_DBG_ECO_CNTL, BIT\((\d+)\), BIT\(\d+\)\);', 'a7xx rb cmp eco bit')
    uav = literal(gpu_c, r'adreno_is_a7xx\(adreno_gpu\)\)\n\t\tuavflagprd_inv = (\d+);', 'uavflagprd_inv')
    gmu_fn = gmu_c[gmu_c.index('static int a6xx_gmu_fw_start('):gmu_c.index('#define A6XX_HFI_IRQ_MASK')]
    fence_upper = literal(gmu_fn, r'\} else if \(adreno_is_a7xx\(adreno_gpu\)\) \{\n\t\tfence_range_upper = (0x[0-9a-f]+);', 'a7xx fence upper')
    fence_lower = literal(gmu_fn, r'\} else if \(adreno_is_a7xx\(adreno_gpu\)\) \{\n\t\tfence_range_upper = 0x[0-9a-f]+;\n\t\tfence_range_lower = (0x[0-9a-f]+);', 'a7xx fence lower')
    fence = (1 << 31) | (fence_upper << 18) | fence_lower
    pas_id = literal(gpu_c, r'#define GPU_PAS_ID (\d+)\n', 'pas id')
    lines = ['/* SPDX-License-Identifier: MIT */', '#ifndef NATIVE_ADRENO_A740_HWINIT_H', '#define NATIVE_ADRENO_A740_HWINIT_H',
             '#include <stdint.h>',
             '/* Generated by scripts/derive-a740-hwinit.py from the pinned a6xx.xml/adreno_common.xml/a6xx_gmu.xml (A7XX',
             ' * variants) and a6xx_catalog.c (a740_hwcg, a730_protect). Dword register offsets. Do not edit by hand. */']
    for name, offset in defines:
        lines.append('#define A740_%s 0x%05x' % (name, offset))
    lines += ['/* the 0x43050a01 catalog entry and the a740 family branches of hw_init, a6xx_set_hwcg, a6xx_set_ubwc_config,',
              ' * A7XX_INT_MASK, the A7XX_APRIV masks and a6xx_gmu_fw_start, each read from its own pinned source line */',
              '#define NATIVE_ADRENO_A740_GMEM_BYTES 0x%x' % gmem,
              '#define NATIVE_ADRENO_A740_GMEM_BASE 0x%xull' % gmem_base,
              '#define NATIVE_ADRENO_A740_GMU_CHIP_ID 0x%08x' % gmu_chipid,
              '#define NATIVE_ADRENO_A740_GMU_CGC_MODE 0x%08x' % cgc_mode,
              '#define NATIVE_ADRENO_A740_ZAP_PAS_ID %d' % pas_id,
              '#define NATIVE_ADRENO_A740_CLOCK_CNTL_ON 0x%08x' % clock_cntl_on,
              '#define NATIVE_ADRENO_A740_CGC_DELAY 0x%05x' % cgc_delay,
              '#define NATIVE_ADRENO_A740_CGC_HYST 0x%04x' % cgc_hyst,
              '#define NATIVE_ADRENO_A740_GBIF_CLIENT_QOS 0x%07x' % qos,
              '#define NATIVE_ADRENO_A740_UCHE_GBIF_GX_CONFIG 0x%07x' % gx_config,
              '#define NATIVE_ADRENO_A740_UCHE_TRAP_BASE 0x%xull' % trap_base,
              '#define NATIVE_ADRENO_A740_UCHE_CACHE_WAYS 0x%x' % (1 << ways),
              '#define NATIVE_ADRENO_A740_CP_AHB_CNTL 0x%x' % ahb,
              '#define NATIVE_ADRENO_A740_RBBM_PERFCTR_CNTL 0x%x' % perfctr,
              '#define NATIVE_ADRENO_A740_HANG_INT_CNTL 0x%08x' % ((1 << 30) | hang),
              '#define NATIVE_ADRENO_A740_UCHE_CLIENT_PF 0x%x' % client_pf,
              '#define NATIVE_ADRENO_A740_CP_PROTECT_CNTL 0x%x' % protect_cntl,
              '#define NATIVE_ADRENO_A740_UCHE_CMDQ_CONFIG 0x%05x' % cmdq,
              '#define NATIVE_ADRENO_A740_APRIV_MASK 0x%02x' % apriv,
              '#define NATIVE_ADRENO_A740_BR_APRIV_MASK 0x%02x' % br_apriv,
              '#define NATIVE_ADRENO_A740_RB_CMP_DBG_ECO_BITS 0x%x' % (1 << rb_cmp),
              '#define NATIVE_ADRENO_A740_UAVFLAGPRD_INV %d' % uav,
              '#define NATIVE_ADRENO_A740_APERTURE_PIPE_SHIFT %d' % pipe_shift,
              '#define NATIVE_ADRENO_A740_PIPE_BR %d' % pipe_br,
              '#define NATIVE_ADRENO_A740_PIPE_BV %d' % pipe_bv,
              '#define NATIVE_ADRENO_A740_INT_MASK 0x%08x' % int_mask,
              '#define NATIVE_ADRENO_A740_CP_ERROR_MASK 0x%08x' % cp_errors,
              '#define NATIVE_ADRENO_A740_GMU_FENCE_RANGE 0x%08x' % fence]
    lines.append('static const uint32_t NativeAdrenoA740Hwcg[][2]={')
    lines += ['    {0x%05x,0x%08x},   /* %s */' % (o, v, n) for n, o, v in hwcg]
    lines.append('};')
    lines.append('#define NATIVE_ADRENO_A740_HWCG_COUNT %d' % len(hwcg))
    lines.append('/* {CP_PROTECT index, value} in a6xx_set_cp_protect order. */')
    lines.append('static const uint32_t NativeAdrenoA740Protect[][2]={')
    lines += ['    {%2d,0x%08x},' % w for w in writes]
    lines.append('};')
    lines.append('#define NATIVE_ADRENO_A740_PROTECT_COUNT %d' % len(writes))
    lines.append('#endif')
    text = '\n'.join(lines) + '\n'
    out = OUT
    if '--output' in sys.argv[1:]:
        out = Path(sys.argv[sys.argv.index('--output') + 1])
    if '--check' in sys.argv[1:]:
        if out.read_text() != text:
            raise SystemExit('NativeAdrenoA740HwInit.h is stale')
        print('PASS: A740 hw_init table matches the pinned sources')
        return
    out.write_text(text)
    print('PASS: %d registers, %d hwcg entries, %d protect writes' % (len(defines), len(hwcg), len(writes)))

main()
