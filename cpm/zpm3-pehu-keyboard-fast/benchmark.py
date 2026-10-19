"""Matched CPU-cycle and ATA-command measurements on disposable factory disks."""
from pathlib import Path
import base64,configparser,hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'archive-tools'),str(ROOT/'cpm/gide/tools'),str(ROOT/'cpm/suc-native')]
from test_mz800emu_boot import Emulator
from media import hard_volume
from monitor_boot import reset_to_handover,enter_gide
out=ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/benchmark';out.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,str(ROOT/'cpm/gide/third_party/pyz80.py'),'--obj='+str(out/'BENCH.COM'),'--mapfile='+str(out/'bench.map'),str(HERE/'benchmark.asm')],check=True,stdout=subprocess.DEVNULL)
labels={n:int(a,16) for a,n in (x.split('=',1) for x in (out/'bench.map').read_text().splitlines())}
for n,digest in json.loads((HERE/'reference/performance-baseline/SHA256.json').read_text()).items():assert hashlib.sha256((HERE/'reference/performance-baseline'/n).read_bytes()).hexdigest()==digest,n
payload=bytes(range(128))*600
results=[]
for variant,folder,config,stem in [('baseline',HERE/'reference/performance-baseline',HERE/'reference/performance-baseline/profile.ini','gide-zpm3-pehu-screen-fast'),('fast',HERE,ROOT/'build-records/mz800emu/zpm3-pehu-keyboard-fast/interactive-0.1.0/mz700.ini','gide-zpm3-pehu-keyboard-fast')]:
 for repeat in range(3):
  dest=out/f'{variant}-{repeat+1}';dest.mkdir(exist_ok=True)
  raw=bytearray((HERE/'reference/current-fast.img').read_bytes());raw[16777216:]=(folder/'build'/(stem+'.img')).read_bytes()[16777216:];part=raw[:8388608];v=hard_volume(part)
  v.write('CPM3.SYS',(folder/'build/cpm3.sys').read_bytes())
  v.write('RTC.COM',(HERE/'build/RTC.COM').read_bytes())
  v.write('BENCH.COM',(out/'BENCH.COM').read_bytes());v.write('BENCHIN.DAT',payload);raw[:8388608]=part
  disk=dest/'disk.img';disk.write_bytes(raw)
  ini=configparser.ConfigParser(interpolation=None);ini.read(config);ini['GIDE']['hdd0_filepath']=str(disk)
  # Always pin each build's boot payload, independently of GUI state.
  ini['ROM']['user_defined_allinone_filepath']=str(folder/'build'/(stem+'-stock-rom.bin'))
  ini['ROM']['boot_rom_f000_filepath']=str(folder/'build'/(stem+'-bootrom.bin'));ini['ROM']['boot_rom_mode']='F000'
  with (dest/'input.ini').open('w') as f:ini.write(f)
  report=json.loads((folder/'build/build.json').read_text());symbols=report['symbols']
  e=Emulator(ROOT/'emulators/Working/mz800emu/build-mac/build-mz700emu-pal/mz700emu-pal',dest,['--home-dir',str(ROOT/'emulators/Working/mz800emu'),'--config',str(dest/'input.ini')])
  def call(c,d=None):
   r=e.call(c,d);assert r.get('success'),r;return r.get('data',{})
  def run(n):
   while n:k=min(n,1000);call('run',{'frames':k});n-=k
  def mem(a,n):
   result=bytearray()
   while n:
    pa=a+(0x10000 if 0x2000<=a<0xc000 else 0);k=min(n,4096-(a&4095));rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='memext_ram' and x['sub_id']==pa//4096)
    result+=base64.b64decode(call('region_read',{'region_id':rid,'offset':pa&4095,'length':k})['data_b64']);a+=k;n-=k
   return bytes(result)
  def put_common(a,data):
   while data:
    k=min(len(data),4096-(a&4095));rid=next(x['id'] for x in call('regions_list')['regions'] if x['kind']=='memext_ram' and x['sub_id']==a//4096)
    call('region_write',{'region_id':rid,'offset':a&4095,'data_b64':base64.b64encode(data[:k]).decode()});a+=k;data=data[k:]

  def until(addr):
   if call('get_registers')['PC']==addr:return
   for _ in range(50):
    run(500)
    pc=call('get_registers')['PC']
    assert pc!=labels['failure_loop'],('benchmark failure',variant,hex(pc))
    if pc==addr:return
   raise AssertionError(('breakpoint timeout',variant,hex(addr),hex(pc)))
  try:
   reset_to_handover(call);enter_gide(call);run(3000)
   first=call('bp_add',{'addr':labels['read_start']})['id']
   call('input_send_keys',{'text':'BENCH','frame_per_key':30});run(10);call('input_send_key',{'key':'RETURN','frames':30})
   until(labels['read_start']);call('bp_remove',{'id':first})
   ceiling=int.from_bytes(mem(0x8000,2),'little');row=dict(variant=variant,repeat=repeat+1,application_ceiling=ceiling,application_tpa_bytes=ceiling-256,ccp_tpa_bytes=report['zccp_tpa_bytes'],layout=report['layout'],segments={})
   assert ceiling-256==60672
   stack=report['common_symbols']['gate_stack'];stack_end=report['common_symbols']['gate_stack_end'];put_common(stack,b'\xa5'*(stack_end-stack))
   for name,start,end in [('sequential_read','read_start','read_end'),('sequential_write_flush','write_start','write_end'),('print_1000','print_start','print_end'),('erase_1999_cells_10_times','erase_start','erase_end'),('scroll_100_times','scroll_start','scroll_end'),('clear_screen_100_times','clear_start','clear_end')]:
    if call('get_registers')['PC']!=labels[start]:
     bp=call('bp_add',{'addr':labels[start]})['id'];until(labels[start]);call('bp_remove',{'id':bp})
    stop=call('bp_add',{'addr':labels[end]})['id']
    cycles=call('get_raster_pos')['total_cycles'];call('profiler_pc_start',{'reset':True});until(labels[end]);prof=call('profiler_pc_stop');cycles=(call('get_raster_pos')['total_cycles']-cycles)&0xffffffff
    call('profiler_pc_export',{'path':str(dest/(name+'.csv')),'sort':'addr'})
    counts={}
    for key in ['ata_read','ata_write']:
     pc=symbols[key];r=call('profiler_pc_get',{'from':pc,'to':pc,'limit':1});counts[key]=sum(x['count'] for x in r['rows'])
    for key in ['bank_raw','map_first','move']:
     pc=report['common_symbols'][key];r=call('profiler_pc_get',{'from':pc,'to':pc,'limit':1});counts[key]=sum(x['count'] for x in r['rows'])
    row['segments'][name]=dict(tstates=cycles,ata_commands=counts,profiler=prof)
    row['segments'][name].update(dict(bytes=76800) if name.startswith('sequential') else dict(characters=1000) if name=='print_1000' else dict(cells_per_erase=1999,erasures=10) if name.startswith('erase') else dict(clears=100,physical_character_cells=2048) if name.startswith('clear') else dict(scrolls=100))
    call('bp_remove',{'id':stop})
   run(1);assert mem(0x8004,1)==b'\xa5'
   volume=hard_volume(bytearray(disk.read_bytes()[:8388608]));assert volume.read('BENCHOUT.DAT')==payload;assert volume.read('BENCHIN.DAT')==payload
   row['host_file_verification']=True
   watermark=mem(stack,stack_end-stack);first=next((i for i,b in enumerate(watermark) if b!=0xa5),len(watermark));row['gate_stack_watermark_bytes']=len(watermark)-first
   assert first>=16,('Insufficient stack margin',variant,first,len(watermark))
   call('screenshot_save_to_file',{'path':str(dest/'result.png'),'scale':'2'})
   (dest/'result.json').write_text(json.dumps(row,indent=2)+'\n');results.append(row);print(variant,repeat+1,json.dumps(row['segments']),flush=True)
  finally:e.close()
by_variant={v:[r for r in results if r['variant']==v] for v in ['baseline','fast']}
for rows in by_variant.values():
 for name in rows[0]['segments']:
  assert len({r['segments'][name]['tstates'] for r in rows})==1,(name,[r['segments'][name]['tstates'] for r in rows])
comparison={n:dict(baseline_tstates=by_variant['baseline'][0]['segments'][n]['tstates'],fast_tstates=by_variant['fast'][0]['segments'][n]['tstates'],speedup=by_variant['baseline'][0]['segments'][n]['tstates']/by_variant['fast'][0]['segments'][n]['tstates'],cycle_reduction_percent=100*(1-by_variant['fast'][0]['segments'][n]['tstates']/by_variant['baseline'][0]['segments'][n]['tstates'])) for n in by_variant['baseline'][0]['segments']}
summary=dict(passed=True,comparison=comparison,method='Three fresh emulator processes per build; identical 600-record COM workload; CPU total_cycles between execution breakpoints, includes open/close and explicit write flush, excludes typing/CCP load; unaligned DMA4001h. ATA calls counted with PC profiler. Emulator cycles, not physical hardware or host wall time.',results=results)
(out/'results.json').write_text(json.dumps(summary,indent=2)+'\n')

print(json.dumps(comparison,indent=2))
