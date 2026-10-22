#!/usr/bin/env python3
"""Derive the A650 hw_init register table (a6xx_gpu.c hw_init, a6xx_set_hwcg, a6xx_set_cp_protect, a6xx_set_ubwc_config, the
A6XX_INT_MASK and the GMU boot registers a6xx_gmu.c uses for the a650 family) from the pinned sources, as
derive-a740-hwinit.py does for the A740.

Offsets come from the pinned XMLs with exact A6XX variant selection (a6xx.xml first, then adreno_common.xml, a6xx_gmu.xml for
the GMU block); the hwcg, protect and GBIF values from the pinned a6xx_catalog.c (a650_hwcg, a650_protect, a640_gbif and the
0x06050002 entry); the scalar values hw_init writes on the a650 branches from the pinned a6xx_gpu.c and a6xx_gmu.c text itself.
Writes drivers/NativeAdreno/NativeAdrenoA650HwInit.h (or --output PATH); --check compares instead."""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '.cache/adreno-source/drivers/gpu/drm/msm'
XML = SRC / 'registers/adreno'
ORDER = ['A2XX', 'A3XX', 'A4XX', 'A5XX', 'A6XX', 'A7XX', 'A8XX']
TARGET = 'A6XX'
OUT = ROOT / 'drivers/NativeAdreno/NativeAdrenoA650HwInit.h'

def matches(variants):
    if variants is None:
        return True
    for part in variants.split(','):
        part = part.strip()
        if '-' in part:
            left, right = part.split('-', 1)
            low = ORDER.index(left) if left else 0
            high = ORDER.index(right) if right else len(ORDER) - 1
            if low <= ORDER.index(TARGET) <= high:
                return True
        elif part == TARGET:
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
    """bit positions of the named fields of a bitset, or of a reg32 with inline bitfields, A6XX variants only"""
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

def reglist(catalog, name):
    block = re.search(name + r'\[\]\s*=\s*\{(.*?)\{\s*\},?\s*\};', catalog, re.S).group(1)
    entries = []
    for reg, value in re.findall(r'\{\s*REG_A6XX_([A-Z0-9_]+),\s*(0x[0-9a-fA-F]+)\s*\}', block):
        entries.append((reg, resolve(reg, ['a6xx.xml', 'adreno_common.xml']), int(value, 16)))
    if len(entries) != block.count('REG_'):
        raise SystemExit('unparsed ' + name + ' entry')
    return entries

GPU = ['GBIF_HALT', 'RBBM_GBIF_HALT', 'RBBM_SECVID_TSB_CNTL', 'RBBM_SECVID_TSB_TRUSTED_BASE',
       'RBBM_SECVID_TSB_TRUSTED_SIZE', 'RBBM_SECVID_TRUST_CNTL', 'CP_ADDR_MODE_CNTL', 'VSC_ADDR_MODE_CNTL',
       'GRAS_ADDR_MODE_CNTL', 'RB_ADDR_MODE_CNTL', 'PC_ADDR_MODE_CNTL', 'HLSQ_ADDR_MODE_CNTL', 'VFD_ADDR_MODE_CNTL',
       'VPC_ADDR_MODE_CNTL', 'UCHE_ADDR_MODE_CNTL', 'SP_ADDR_MODE_CNTL', 'TPL1_ADDR_MODE_CNTL',
       'RBBM_SECVID_TSB_ADDR_MODE_CNTL', 'RBBM_CLOCK_CNTL', 'GBIF_QSB_SIDE0', 'GBIF_QSB_SIDE1', 'GBIF_QSB_SIDE2',
       'GBIF_QSB_SIDE3', 'RBBM_GBIF_CLIENT_QOS_CNTL', 'RBBM_PERFCTR_GPU_BUSY_MASKED', 'UCHE_WRITE_RANGE_MAX',
       'UCHE_TRAP_BASE', 'UCHE_WRITE_THRU_BASE', 'UCHE_GMEM_RANGE_MIN', 'UCHE_GMEM_RANGE_MAX', 'UCHE_FILTER_CNTL',
       'UCHE_CACHE_WAYS', 'CP_ROQ_THRESHOLDS_1', 'CP_ROQ_THRESHOLDS_2', 'CP_MEM_POOL_SIZE', 'PC_DBG_ECO_CNTL',
       'CP_AHB_CNTL', 'RBBM_PERFCTR_CNTL', 'RB_NC_MODE_CNTL', 'TPL1_NC_MODE_CNTL', 'SP_NC_MODE_CNTL', 'UCHE_MODE_CNTL',
       'RBBM_NC_MODE_CNTL', 'RBBM_INTERFACE_HANG_INT_CNTL', 'UCHE_CLIENT_PF', 'CP_PROTECT_CNTL', 'CP_APRIV_CNTL',
       'RBBM_INT_0_MASK', 'RBBM_INT_0_STATUS', 'RBBM_INT_CLEAR_CMD', 'CP_INTERRUPT_STATUS', 'CP_PROTECT_STATUS',
       'CP_SQE_INSTR_BASE', 'CP_RB_BASE', 'CP_RB_CNTL', 'CP_RB_RPTR_ADDR', 'CP_RB_RPTR', 'CP_RB_WPTR', 'CP_SQE_CNTL',
       'RBBM_STATUS', 'RBBM_STATUS3', 'CP_HW_FAULT', 'CP_SQE_STAT_ADDR', 'CP_SQE_STAT_DATA', 'CP_ALWAYS_ON_COUNTER',
       'RBBM_PERFCTR_SRAM_INIT_CMD', 'RBBM_PERFCTR_SRAM_INIT_STATUS']
GPU_ARRAYS = ['CP_PROTECT', 'CP_SCRATCH', 'CP_PERFCTR_CP_SEL', 'TPL1_BICUBIC_WEIGHTS_TABLE']
GMU = ['GPU_GMU_AO_GMU_CGC_MODE_CNTL', 'GPU_GMU_AO_GMU_CGC_DELAY_CNTL', 'GPU_GMU_AO_GMU_CGC_HYST_CNTL',
       'GPU_GMU_AO_GPU_CX_BUSY_MASK', 'GMU_CX_GMU_POWER_COUNTER_SELECT_0', 'GMU_CX_GMU_POWER_COUNTER_ENABLE',
       'GPU_GMU_GX_SPTPRAC_CLOCK_CONTROL', 'GMU_GENERAL_7', 'GMU_HFI_SFR_ADDR', 'GPU_GMU_CX_GMU_PWR_COL_CP_MSG',
       'GPU_GMU_CX_GMU_PWR_COL_CP_RESP', 'GMU_PWR_COL_INTER_FRAME_CTRL', 'GMU_PWR_COL_INTER_FRAME_HYST',
       'GMU_PWR_COL_SPTPRAC_HYST', 'GMU_RPMH_CTRL', 'GMU_SPTPRAC_PWR_CLK_STATUS', 'GPU_GMU_CX_GMU_CX_FALNEXT_INTF',
       'GPU_GMU_CX_GMU_CX_FAL_INTF', 'GMU_CM3_ITCM_START', 'GMU_CM3_DTCM_START', 'GMU_CM3_SYSRESET',
       'GMU_CM3_BOOT_CONFIG', 'GMU_CM3_FW_INIT_RESULT', 'GMU_CM3_CFG', 'GMU_HFI_QTBL_ADDR', 'GMU_HFI_QTBL_INFO',
       'GMU_HFI_CTRL_INIT', 'GMU_HFI_CTRL_STATUS', 'GMU_HOST2GMU_INTR_SET', 'GMU_GMU2HOST_INTR_INFO',
       'GMU_GMU2HOST_INTR_CLR', 'GMU_GMU2HOST_INTR_MASK', 'GMU_AO_HOST_INTERRUPT_STATUS', 'GMU_AO_HOST_INTERRUPT_CLR',
       'GMU_AO_HOST_INTERRUPT_MASK', 'GMU_AHB_FENCE_RANGE_0', 'GMU_SYS_BUS_CONFIG', 'GMU_ICACHE_CONFIG',
       'GMU_DCACHE_CONFIG', 'GMU_CORE_FW_VERSION', 'GMU_ALWAYS_ON_COUNTER_L', 'GMU_ALWAYS_ON_COUNTER_H',
       'GPU_GMU_CX_GMU_RPMH_POWER_STATE', 'GMU_AO_AHB_FENCE_CTRL', 'GPU_RSCC_RSC_STATUS0_DRV0',
       'RSCC_PDC_SLAVE_ID_DRV0', 'RSCC_HIDDEN_TCS_CMD0_ADDR', 'RSCC_HIDDEN_TCS_CMD0_DATA', 'RSCC_OVERRIDE_START_ADDR',
       'RSCC_PDC_SEQ_START_ADDR', 'RSCC_PDC_MATCH_VALUE_LO', 'RSCC_PDC_MATCH_VALUE_HI', 'RSCC_SEQ_MEM_0_DRV0',
       'RSCC_SEQ_BUSY_DRV0', 'GMU_RSCC_CONTROL_REQ', 'GMU_RSCC_CONTROL_ACK']
# the GPU PDC block (a6xx.xml A6XX_PDC domain), named PDC_GPU_* as a6xx_gmu.c does
PDC = ['GPU_SEQ_START_ADDR', 'GPU_ENABLE_PDC']
# names of A6XX_INT_MASK in the pinned a6xx_gpu.c, in its order
INT_MASK = ['CP_AHB_ERROR', 'RBBM_ATB_ASYNCFIFO_OVERFLOW', 'CP_HW_ERROR', 'CP_IB2', 'CP_IB1', 'CP_RB',
            'CP_CACHE_FLUSH_TS', 'RBBM_ATB_BUS_OVERFLOW', 'RBBM_HANG_DETECT', 'UCHE_OOB_ACCESS', 'UCHE_TRAP_INTR']
CP_ERRORS = ['CP_OPCODE_ERROR', 'CP_UCODE_ERROR', 'CP_HW_FAULT_ERROR', 'CP_REGISTER_PROTECTION_ERROR',
             'CP_AHB_ERROR', 'CP_VSD_PARITY_ERROR', 'CP_ILLEGAL_INSTR_ERROR']

def main():
    catalog = (SRC / 'adreno/a6xx_catalog.c').read_text()
    gpu_c = (SRC / 'adreno/a6xx_gpu.c').read_text()
    gmu_c = (SRC / 'adreno/a6xx_gmu.c').read_text()
    gpu_h = (SRC / 'adreno/a6xx_gpu.h').read_text()
    defines = [(n, resolve(n, ['a6xx.xml', 'adreno_common.xml'])) for n in GPU]
    defines += [(n, resolve(n, ['a6xx.xml'], 'array')) for n in GPU_ARRAYS]
    defines += [(n, resolve(n, ['a6xx_gmu.xml'])) for n in GMU]
    defines += [('PDC_' + n, resolve(n, ['a6xx.xml'])) for n in PDC]
    # the text of the A6XX_INT_MASK macro must name exactly the fields listed above
    mask_text = re.search(r'#define A6XX_INT_MASK \((.*?)\)\n\n', gpu_c, re.S).group(1)
    if re.findall(r'A6XX_RBBM_INT_0_MASK_(\w+)', mask_text) != INT_MASK:
        raise SystemExit('A6XX_INT_MASK fields changed')
    int_mask = bits('a6xx.xml', 'A6XX_RBBM_INT_0_MASK', INT_MASK)
    cp_errors = bits('a6xx.xml', 'A6XX_CP_INT', CP_ERRORS)
    protect_cntl = bits('a6xx.xml', 'a6xx_cp_protect_cntl', ['ACCESS_PROT_EN', 'ACCESS_FAULT_ON_VIOL_EN', 'LAST_SPAN_INF_RANGE'])
    rpmh_ctrl = bits('a6xx_gmu.xml', 'GMU_RPMH_CTRL', ['RPMH_INTERFACE_ENABLE', 'LLC_VOTE_ENABLE', 'DDR_VOTE_ENABLE',
                                                           'MX_VOTE_ENABLE', 'CX_VOTE_ENABLE', 'GFX_VOTE_ENABLE'])
    ifpc_ctrl = bits('a6xx_gmu.xml', 'GMU_PWR_COL_INTER_FRAME_CTRL', ['IFPC_ENABLE', 'HM_POWER_COLLAPSE_ENABLE'])
    gx_off = bits('a6xx_gmu.xml', 'GMU_SPTPRAC_PWR_CLK_STATUS', ['GX_HM_GDSC_POWER_OFF', 'GX_HM_CLK_OFF'])
    perf = (XML / 'a6xx_perfcntrs.xml').read_text()
    always_count = literal(perf, r'<value value="(\d+)" name="PERF_CP_ALWAYS_COUNT"/>', 'PERF_CP_ALWAYS_COUNT')
    hwcg = reglist(catalog, 'a650_hwcg')
    gbif = reglist(catalog, 'a640_gbif')
    pblock = re.search(r'a650_protect_regs\[\]\s*=\s*\{(.*?)\};', catalog, re.S).group(1)
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
    count_max = int(re.search(r'DECLARE_ADRENO_PROTECT\(a650_protect,\s*(\d+)\)', catalog).group(1))
    # a6xx_set_cp_protect: entries 0..count-2 at their index (zeros skipped), the last one at count_max-1.
    writes = [(i, v) for i, v in enumerate(protect[:-1]) if v] + [(count_max - 1, protect[-1])]
    entry = re.search(r'\.chip_ids = ADRENO_CHIP_IDS\((0x06050002)\)([\s\S]*?)\.speedbins', catalog)
    chip_id = int(entry.group(1), 16)
    record = entry.group(2)
    if chip_id != 0x06050002 or '"a650_sqe.fw"' not in record or '"a650_gmu.bin"' not in record or \
            '.zapfw = "a650_zap.mdt"' not in record or '.hwcg = a650_hwcg' not in record or \
            '.protect = &a650_protect' not in record or '.gbif_cx = a640_gbif' not in record:
        raise SystemExit('the a650 catalog entry is not the one this script derives from')
    gmem = re.search(r'\.gmem = SZ_1M \+ SZ_128K,', record)
    if not gmem:
        raise SystemExit('a650 gmem expression changed')
    gmem = (1 << 20) + (128 << 10)
    cgc_mode = int(re.search(r'\.gmu_cgc_mode = (0x[0-9a-f]+)', record).group(1), 16)
    prim_fifo = int(re.search(r'\.prim_fifo_threshold = (0x[0-9a-f]+)', record).group(1), 16)
    quirks = re.search(r'\.quirks = ([^,]+(?:,\s*)?[^,]*?),\n\s*\.funcs', record).group(1)
    if 'ADRENO_QUIRK_HAS_HW_APRIV' not in quirks or 'ADRENO_QUIRK_IFPC' in quirks:
        raise SystemExit('a650 quirks changed (hw_apriv expected, ifpc not expected)')
    # a6xx_gpu.c hw_init, a6xx_set_hwcg and a6xx_set_cp_protect on the a650 branches: each value is read from its own line
    hwcg_fn = gpu_c[gpu_c.index('static void a6xx_set_hwcg('):gpu_c.index('static void a6xx_set_cp_protect(')]
    clock_cntl_on = literal(hwcg_fn, r'else\n\t\tclock_cntl_on = (0x[0-9a-f]+);', 'clock_cntl_on default')
    cgc_delay = literal(hwcg_fn, r'else\n\t\tcgc_delay = (0x[0-9a-f]+);', 'cgc_delay default')
    cgc_hyst = literal(hwcg_fn, r'else\n\t\tcgc_hyst = (0x[0-9a-f]+);', 'cgc_hyst default')
    init_fn = gpu_c[gpu_c.index('static int hw_init('):gpu_c.index('static int a6xx_hw_init(')]
    qos = literal(init_fn, r'adreno_is_a650_family\(adreno_gpu\)\) \{\n\t\tgpu_write\(gpu, REG_A6XX_RBBM_GBIF_CLIENT_QOS_CNTL, (0x[0-9a-f]+)\);', 'a650 gbif qos')
    write_range = literal(init_fn, r'REG_A6XX_UCHE_WRITE_RANGE_MAX, adreno_gpu->uche_trap_base \+ (0x[0-9a-f]+)\)', 'uche write range')
    trap_base = literal(gpu_c, r'adreno_gpu->uche_trap_base = (0x[0-9a-f]+)ull;', 'uche trap base')
    uche_filter = literal(init_fn, r'REG_A6XX_UCHE_FILTER_CNTL, (0x[0-9a-f]+)\);', 'uche filter')
    uche_ways = literal(init_fn, r'REG_A6XX_UCHE_FILTER_CNTL, 0x[0-9a-f]+\);\n\t\tgpu_write\(gpu, REG_A6XX_UCHE_CACHE_WAYS, (0x[0-9a-f]+)\);', 'uche ways')
    roq2 = literal(init_fn, r'adreno_is_a650_family\(adreno_gpu\)\) \{\n\t\tgpu_write\(gpu, REG_A6XX_CP_ROQ_THRESHOLDS_2, (0x[0-9a-f]+)\);', 'roq 2')
    roq1 = literal(init_fn, r'REG_A6XX_CP_ROQ_THRESHOLDS_2, 0x02000140\);\n\t\tgpu_write\(gpu, REG_A6XX_CP_ROQ_THRESHOLDS_1, (0x[0-9a-f]+)\);', 'roq 1')
    mem_pool = literal(init_fn, r'else if \(!adreno_is_a7xx\(adreno_gpu\)\)\n\t\tgpu_write\(gpu, REG_A6XX_CP_MEM_POOL_SIZE, (\d+)\);', 'mem pool')
    ahb = literal(init_fn, r'REG_A6XX_CP_AHB_CNTL, (0x[0-9a-f]+)\);', 'ahb cntl')
    perfctr = literal(init_fn, r'REG_A6XX_RBBM_PERFCTR_CNTL, (0x[0-9a-f]+)\);', 'perfctr cntl')
    hang = literal(init_fn, r'else\n\t\tgpu_write\(gpu, REG_A6XX_RBBM_INTERFACE_HANG_INT_CNTL, \(1 << 30\) \| (0x[0-9a-f]+)\);', 'hang detect default')
    client_pf = re.search(r'REG_A6XX_UCHE_CLIENT_PF, BIT\((\d+)\) \| (0x[0-9a-f]+)\);', init_fn)
    client_pf = (1 << int(client_pf.group(1))) | int(client_pf.group(2), 16)
    bicubic = re.findall(r'REG_A6XX_TPL1_BICUBIC_WEIGHTS_TABLE\((\d)\),\s*(0x[0-9a-f]+|0)\);', init_fn)
    if [int(i) for i, _ in bicubic] != [0, 1, 2, 3, 4]:
        raise SystemExit('bicubic weights table changed')
    bicubic = [int(v, 0) for _, v in bicubic]
    busy_mask = literal(init_fn, r'REG_A6XX_GPU_GMU_AO_GPU_CX_BUSY_MASK, (0x[0-9a-f]+)\);', 'cx busy mask')
    counter_sel = re.search(r'REG_A6XX_GMU_CX_GMU_POWER_COUNTER_SELECT_0, (0x[0-9a-f]+), BIT\((\d+)\)\);', init_fn)
    counter_sel = (int(counter_sel.group(1), 16), 1 << int(counter_sel.group(2)))
    apriv = re.search(r'\} else\n\t\t\tgpu_write\(gpu, REG_A6XX_CP_APRIV_CNTL,\n\t\t\t\t  ((?:BIT\(\d+\)(?: \| )?)+)\);', init_fn).group(1)
    apriv = sum(1 << int(b) for b in re.findall(r'BIT\((\d+)\)', apriv))
    uav = literal(gpu_c, r'adreno_is_a7xx\(adreno_gpu\)\)\n\t\tuavflagprd_inv = (\d+);', 'uavflagprd_inv')
    # a6xx_gmu.c for the a650 family: fence range, power config, TCM retention through GMU_GENERAL_7
    gmu_fn = gmu_c[gmu_c.index('static int a6xx_gmu_fw_start('):gmu_c.index('#define A6XX_HFI_IRQ_MASK')]
    fence_upper = literal(gmu_fn, r'\} else \{\n\t\tfence_range_upper = (0x[0-9a-f]+);', 'fence upper')
    fence_lower = literal(gmu_fn, r'\} else \{\n\t\tfence_range_upper = 0x[0-9a-f]+;\n\t\tfence_range_lower = (0x[0-9a-f]+);', 'fence lower')
    fence = (1 << 31) | (fence_upper << 18) | fence_lower
    if 'gmu_write(gmu, REG_A6XX_GMU_GENERAL_7, 1);' not in gmu_fn:
        raise SystemExit('a6xx TCM retention write changed')
    power_fn = gmu_c[gmu_c.index('static void a6xx_gmu_power_config('):gmu_c.index('struct block_header {')]
    inter_frame = literal(power_fn, r'REG_A6XX_GMU_PWR_COL_INTER_FRAME_CTRL, (0x[0-9a-f]+)\);', 'inter frame ctrl')
    hyst = literal(gmu_c, r'#define GMU_PWR_COL_HYST (0x[0-9a-f]+)', 'pwr col hyst')
    pas_id = literal(gpu_c, r'#define GPU_PAS_ID (\d+)\n', 'pas id')
    seq = re.search(r'adreno_is_a7xx\(adreno_gpu\)\) \{\n((?:\t\tgmu_write_rscc\(gmu, seqmem0_drv0_reg(?: \+ \d)?, 0x[0-9a-f]+\);\n)+)', gmu_c).group(1)
    seq = [int(v, 16) for v in re.findall(r'(0x[0-9a-f]{8})', seq)]
    if len(seq) != 5:
        raise SystemExit('rsc sequencer ucode length changed')
    rsc_cmd0_data = literal(gmu_c, r'adreno_is_a740_family\(adreno_gpu\) \? 0x[0-9a-f]+ : (0x[0-9a-f]+)\);', 'hidden tcs cmd0 data')
    pdc_enable = literal(gmu_c, r'pdc_write\(pdcptr, REG_A6XX_PDC_GPU_ENABLE_PDC, (0x[0-9a-f]+)\);', 'pdc enable')
    rsc_setup = re.findall(r'gmu_write_rscc\(gmu, REG_A6XX_(RSCC_PDC_SLAVE_ID_DRV0|RSCC_OVERRIDE_START_ADDR|RSCC_PDC_SEQ_START_ADDR|RSCC_PDC_MATCH_VALUE_LO|RSCC_PDC_MATCH_VALUE_HI), (0x[0-9a-f]+|\d)\);', gmu_c)
    rsc_setup = {n: int(v, 0) for n, v in rsc_setup}
    if sorted(rsc_setup) != ['RSCC_OVERRIDE_START_ADDR', 'RSCC_PDC_MATCH_VALUE_HI', 'RSCC_PDC_MATCH_VALUE_LO', 'RSCC_PDC_SEQ_START_ADDR', 'RSCC_PDC_SLAVE_ID_DRV0']:
        raise SystemExit('rsc setup writes changed')
    # a6xx_cp_init: the eight CP_ME_INIT payload words the a650 runs with (no power-up list, no CP_THREAD_CONTROL)
    cp_fn = gpu_c[gpu_c.index('static int a6xx_cp_init('):gpu_c.index('static int a7xx_cp_init(')]
    if 'OUT_PKT7(ring, CP_ME_INIT, 8);' not in cp_fn:
        raise SystemExit('a6xx_cp_init packet length changed')
    cp_init = [int(v, 16) for v in re.findall(r'OUT_RING\(ring, (0x[0-9a-f]{8})\);', cp_fn)]
    if len(cp_init) != 8:
        raise SystemExit('a6xx_cp_init payload changed')
    if '#define PWRUP_REGLIST_SIZE' not in gpu_h:
        raise SystemExit('a6xx_gpu.h changed')
    lines = ['/* SPDX-License-Identifier: MIT */', '#ifndef NATIVE_ADRENO_A650_HWINIT_H', '#define NATIVE_ADRENO_A650_HWINIT_H',
             '#include <stdint.h>',
             '/* Generated by scripts/derive-a650-hwinit.py from the pinned a6xx.xml/adreno_common.xml/a6xx_gmu.xml/a6xx_perfcntrs.xml',
             ' * (A6XX variants), a6xx_catalog.c (the 0x06050002 entry, a650_hwcg, a650_protect, a640_gbif), a6xx_gpu.c (hw_init,',
             ' * a6xx_set_hwcg, a6xx_set_cp_protect, a6xx_set_ubwc_config, A6XX_INT_MASK) and a6xx_gmu.c (a6xx_gmu_fw_start,',
             ' * a6xx_gmu_power_config, a6xx_gmu_rpmh_init). Dword register offsets. Do not edit by hand. */']
    for name, offset in defines:
        lines.append('#define A650_%s 0x%05x' % (name, offset))
    lines += ['/* the a650 catalog entry */',
              '#define NATIVE_ADRENO_A650_CATALOG_CHIP_ID 0x%08x' % chip_id,
              '#define NATIVE_ADRENO_A650_GMEM_BYTES 0x%x' % gmem,
              '#define NATIVE_ADRENO_A650_GMU_CGC_MODE 0x%08x' % cgc_mode,
              '#define NATIVE_ADRENO_A650_PRIM_FIFO_THRESHOLD 0x%08x' % prim_fifo,
              '#define NATIVE_ADRENO_A650_ZAP_PAS_ID %d' % pas_id,
              '/* a6xx_set_hwcg defaults for the a650 */',
              '#define NATIVE_ADRENO_A650_CLOCK_CNTL_ON 0x%08x' % clock_cntl_on,
              '#define NATIVE_ADRENO_A650_CGC_DELAY 0x%05x' % cgc_delay,
              '#define NATIVE_ADRENO_A650_CGC_HYST 0x%04x' % cgc_hyst,
              '/* hw_init a650 branches */',
              '#define NATIVE_ADRENO_A650_GBIF_CLIENT_QOS 0x%x' % qos,
              '#define NATIVE_ADRENO_A650_UCHE_TRAP_BASE 0x%xull' % trap_base,
              '#define NATIVE_ADRENO_A650_UCHE_WRITE_RANGE_SPAN 0x%x' % write_range,
              '#define NATIVE_ADRENO_A650_UCHE_FILTER_CNTL 0x%x' % uche_filter,
              '#define NATIVE_ADRENO_A650_UCHE_CACHE_WAYS 0x%x' % uche_ways,
              '#define NATIVE_ADRENO_A650_CP_ROQ_THRESHOLDS_1 0x%08x' % roq1,
              '#define NATIVE_ADRENO_A650_CP_ROQ_THRESHOLDS_2 0x%08x' % roq2,
              '#define NATIVE_ADRENO_A650_CP_MEM_POOL_SIZE %d' % mem_pool,
              '#define NATIVE_ADRENO_A650_CP_AHB_CNTL 0x%x' % ahb,
              '#define NATIVE_ADRENO_A650_RBBM_PERFCTR_CNTL 0x%x' % perfctr,
              '#define NATIVE_ADRENO_A650_PERF_CP_ALWAYS_COUNT %d' % always_count,
              '#define NATIVE_ADRENO_A650_HANG_INT_CNTL 0x%08x' % ((1 << 30) | hang),
              '#define NATIVE_ADRENO_A650_UCHE_CLIENT_PF 0x%x' % client_pf,
              '#define NATIVE_ADRENO_A650_CX_BUSY_MASK 0x%08x' % busy_mask,
              '#define NATIVE_ADRENO_A650_POWER_COUNTER_SELECT_MASK 0x%x' % counter_sel[0],
              '#define NATIVE_ADRENO_A650_POWER_COUNTER_SELECT_VALUE 0x%x' % counter_sel[1],
              '#define NATIVE_ADRENO_A650_CP_PROTECT_CNTL 0x%x' % protect_cntl,
              '#define NATIVE_ADRENO_A650_CP_APRIV_CNTL 0x%x' % apriv,
              '#define NATIVE_ADRENO_A650_UAVFLAGPRD_INV %d' % uav,
              '#define NATIVE_ADRENO_A650_INT_MASK 0x%08x' % int_mask,
              '#define NATIVE_ADRENO_A650_CP_ERROR_MASK 0x%08x' % cp_errors,
              '/* a6xx_gmu.c on the a650 family: TCM retention is GMU_GENERAL_7, the GMU chip id goes to GMU_HFI_SFR_ADDR, the log',
              ' * base to GPU_GMU_CX_GMU_PWR_COL_CP_MSG, the RSC sequencer sits at RSCC_SEQ_MEM_0_DRV0 and the PDC is in AOP */',
              '#define NATIVE_ADRENO_A650_GMU_FENCE_RANGE 0x%08x' % fence,
              '#define NATIVE_ADRENO_A650_GMU_INTER_FRAME_CTRL 0x%08x' % inter_frame,
              '#define NATIVE_ADRENO_A650_GMU_IFPC_CTRL_BITS 0x%x' % ifpc_ctrl,
              '#define NATIVE_ADRENO_A650_GMU_PWR_COL_HYST 0x%08x' % hyst,
              '#define NATIVE_ADRENO_A650_GMU_RPMH_CTRL_BITS 0x%x' % rpmh_ctrl,
              '#define NATIVE_ADRENO_A650_GMU_GX_OFF_BITS 0x%x' % gx_off,
              '#define NATIVE_ADRENO_A650_RSC_HIDDEN_TCS_CMD0_DATA 0x%08x' % rsc_cmd0_data,
              '#define NATIVE_ADRENO_A650_PDC_ENABLE 0x%08x' % pdc_enable]
    for name in ['RSCC_PDC_SLAVE_ID_DRV0', 'RSCC_OVERRIDE_START_ADDR', 'RSCC_PDC_SEQ_START_ADDR', 'RSCC_PDC_MATCH_VALUE_LO', 'RSCC_PDC_MATCH_VALUE_HI']:
        lines.append('#define NATIVE_ADRENO_A650_%s_VALUE 0x%x' % (name, rsc_setup[name]))
    lines.append('static const uint32_t NativeAdrenoA650RscSequence[5]={' + ','.join('0x%08x' % v for v in seq) + '};')
    lines.append('/* a6xx_cp_init: the CP_ME_INIT payload. */')
    lines.append('static const uint32_t NativeAdrenoA650CpInit[8]={' + ','.join('0x%08x' % v for v in cp_init) + '};')
    lines.append('static const uint32_t NativeAdrenoA650BicubicWeights[5]={' + ','.join('0x%08x' % v for v in bicubic) + '};')
    lines.append('static const uint32_t NativeAdrenoA650Hwcg[][2]={')
    lines += ['    {0x%05x,0x%08x},   /* %s */' % (o, v, n) for n, o, v in hwcg]
    lines.append('};')
    lines.append('#define NATIVE_ADRENO_A650_HWCG_COUNT %d' % len(hwcg))
    lines.append('/* a640_gbif, written before the GMU wakes (a6xx_gmu_fw_start gbif_cx). */')
    lines.append('static const uint32_t NativeAdrenoA650GbifCx[][2]={')
    lines += ['    {0x%05x,0x%08x},   /* %s */' % (o, v, n) for n, o, v in gbif]
    lines.append('};')
    lines.append('#define NATIVE_ADRENO_A650_GBIF_CX_COUNT %d' % len(gbif))
    lines.append('/* {CP_PROTECT index, value} in a6xx_set_cp_protect order. */')
    lines.append('static const uint32_t NativeAdrenoA650Protect[][2]={')
    lines += ['    {%2d,0x%08x},' % w for w in writes]
    lines.append('};')
    lines.append('#define NATIVE_ADRENO_A650_PROTECT_COUNT %d' % len(writes))
    lines.append('#endif')
    text = '\n'.join(lines) + '\n'
    out = OUT
    if '--output' in sys.argv[1:]:
        out = Path(sys.argv[sys.argv.index('--output') + 1])
    if '--check' in sys.argv[1:]:
        if out.read_text() != text:
            raise SystemExit('NativeAdrenoA650HwInit.h is stale')
        print('PASS: A650 hw_init table matches the pinned sources')
        return
    out.write_text(text)
    print('PASS: %d registers, %d hwcg entries, %d gbif entries, %d protect writes' % (len(defines), len(hwcg), len(gbif), len(writes)))

main()
