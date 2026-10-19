"""Exercise the stock Sharp monitor before entering the separate GIDE ROM."""
from pathlib import Path
import base64,json
ROOT=Path(__file__).resolve().parents[2]
VERSION=json.loads((Path(__file__).resolve().parent/'build/build.json').read_text())['version'].split('-')[0]
ACTIVE_CONFIG=ROOT/'build-records/mz800emu/cpm3-suc-native'/('interactive-'+VERSION)/'mz700.ini'
def reset_to_handover(call):
    call('pause');call('set_speed',{'mode':'max'});call('reset')
    original=(ROOT/'build-records/mz800emu/roms/mz700-13a-eu-font-1e05.bin').read_bytes()
    def monitor():
        return base64.b64decode(call('mem_read',{'addr':0,'len':4096})['data_b64'])
    assert call('get_registers')['PC']==0,'Reset did not start at0000h'
    assert monitor()==original[:4096],'Monitor ROM differs before startup'
    automatic=base64.b64decode(call('mem_read',{'addr':0xe800,'len':1})['data_b64'])==b'\x00'
    bid=call('bp_add',{'addr':0xe800})['id'] if automatic else None
    call('run',{'frames':1000})
    if automatic:
        assert call('get_registers')['PC']==0xe800,'Monitor did not chain into E800 boot ROM'
        call('bp_remove',{'id':bid})
    else:assert call('get_registers')['PC']<0x1000,'Machine did not wait in Sharp monitor'
    assert monitor()==original[:4096],'Monitor ROM changed before boot'
def enter_gide(call):
    if call('get_registers')['PC']==0xe800:return
    call('input_send_keys',{'text':'F','frame_per_key':30})
    call('run',{'frames':10})
    call('input_send_key',{'key':'RETURN','frames':30})
