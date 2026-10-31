import asyncio
import copy
import unittest
from types import SimpleNamespace
from dbus_next import MessageType
from backend import Backend, plain, mapping_variant, shortcut

D = {'path':'/device','Name':'Logitech G502 X','Profiles':[{'path':'/profile','Index':0,'IsActive':True,'IsDirty':False,'Disabled':False,
'Resolutions':[{'path':'/resolution','Index':0,'Resolution':800,'Resolutions':[400,800,1600],'IsActive':True,'IsDisabled':False}],
'Buttons':[{'path':'/left','Index':0,'Mapping':[1,1],'ActionTypes':[0,1,2,4]}, {'path':'/side','Index':3,'Mapping':[1,4],'ActionTypes':[0,1,2,4]}]}]}
class Bus:
    def add_message_handler(self,handler): self.handler=handler
    async def call(self,msg): return SimpleNamespace(message_type=MessageType.METHOD_RETURN)
class Fake(Backend):
    def __init__(self,fail=False): self.data=copy.deepcopy(D);self.bus=Bus();self.fail=fail;self.commits=0
    async def snapshot(self): return copy.deepcopy([self.data])
    def lookup(self,path):
        p=self.data['Profiles'][0]
        return next(x for x in [self.data,p]+p['Resolutions']+p['Buttons'] if x['path']==path)
    async def props(self,path,kind): return copy.deepcopy(self.lookup(path))
    async def set(self,path,kind,name,value):
        self.lookup(path)[name]=plain(value);self.data['Profiles'][0]['IsDirty']=True
    async def method(self,path,kind,name):
        if name=='Commit':
            self.commits+=1
            self.data['Profiles'][0]['IsDirty']=False
            if self.fail:self.bus.handler(SimpleNamespace(path='/device',interface='org.freedesktop.ratbag1.Device',member='Resync'))
        else:self.lookup(path)['IsActive']=True

class Tests(unittest.TestCase):
    def request(self,**kw): return dict(device='/device',profile='/profile',**kw)
    def test_dpi_commit_readback(self):
        f=Fake();result=asyncio.run(f.change(self.request(op='dpi',target='/resolution',dpi=1600)))
        self.assertEqual(result[0]['Profiles'][0]['Resolutions'][0]['Resolution'],1600);self.assertEqual(f.commits,1)
    def test_reject_unsupported_dpi(self):
        f=Fake()
        with self.assertRaises(ValueError):asyncio.run(f.change(self.request(op='dpi',target='/resolution',dpi=999)))
        self.assertEqual(f.commits,0)
    def test_protect_last_left_click(self):
        f=Fake()
        with self.assertRaises(ValueError):asyncio.run(f.change(self.request(op='button',target='/left',mapping=[0,0])))
        self.assertEqual(f.commits,0)
    def test_button_mapping(self):
        f=Fake();asyncio.run(f.change(self.request(op='button',target='/side',mapping=[1,2])))
        self.assertEqual(f.lookup('/side')['Mapping'],[1,2])
    def test_resync_not_success(self):
        with self.assertRaisesRegex(RuntimeError,'rejected'):
            asyncio.run(Fake(True).change(self.request(op='dpi',target='/resolution',dpi=400)))
    def test_pending_changes(self):
        f=Fake();f.data['Profiles'][0]['IsDirty']=True
        with self.assertRaisesRegex(RuntimeError,'pending'):
            asyncio.run(f.change(self.request(op='dpi',target='/resolution',dpi=400)))
    def test_shortcut(self):
        self.assertEqual(shortcut('LEFTCTRL+C'),[[1,29],[1,46],[2,46],[2,29]])
        for text in ['','BOGUS','C+C']:
            with self.assertRaises(ValueError):shortcut(text)
    def test_variant_wire_shape(self):
        v=mapping_variant(4,shortcut('F13'))
        self.assertEqual(v.signature,'(uv)');self.assertEqual(v.value[1].signature,'a(uu)')
        self.assertEqual(plain(v),[4,[[1,183],[2,183]]])
if __name__=='__main__':unittest.main()
