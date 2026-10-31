"""Small ratbagd API v2 client. No raw HID writes or input interception."""
import asyncio
from dbus_next import Message, MessageType, Variant, BusType
from dbus_next.aio import MessageBus

SERVICE = 'org.freedesktop.ratbag1'
ROOT = '/org/freedesktop/ratbag1'
PROPS = 'org.freedesktop.DBus.Properties'


def plain(value):
    if isinstance(value, Variant):
        return plain(value.value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def shortcut(text):
    from evdev import ecodes
    names = [s.strip().upper() for s in text.split('+')]
    if not 1 <= len(names) <= 5 or len(set(names)) != len(names):
        raise ValueError('Use one key or up to five distinct keys separated by +.')
    codes = []
    for name in names:
        name = name if name.startswith('KEY_') else 'KEY_' + name
        code = getattr(ecodes, name, None)
        if not isinstance(code, int) or not 1 <= code <= 248:
            raise ValueError(f'Unsupported key: {name}. Example: LEFTCTRL+C or F13.')
        codes.append(code)
    return [[1, k] for k in codes] + [[2, k] for k in reversed(codes)]


def mapping_variant(kind, value):
    return Variant('(uv)', [kind, Variant('a(uu)' if kind == 4 else 'u', value)])


class Backend:
    async def call(self, path, interface, member, signature='', body=None):
        reply = await asyncio.wait_for(self.bus.call(Message(destination=SERVICE,
            path=path, interface=interface, member=member,
            signature=signature, body=body or [])), 8)
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f'{reply.error_name}: {reply.body}')
        return reply.body

    async def props(self, path, kind):
        return plain((await self.call(path, PROPS, 'GetAll', 's', [SERVICE+'.'+kind]))[0])

    async def set(self, path, kind, name, value):
        await self.call(path, PROPS, 'Set', 'ssv', [SERVICE+'.'+kind, name, value])

    async def method(self, path, kind, name):
        result = await self.call(path, SERVICE+'.'+kind, name)
        if result and result[0] != 0:
            raise RuntimeError(f'{name} rejected by driver: {result[0]}')

    async def snapshot(self):
        manager = await self.props(ROOT, 'Manager')
        if manager.get('APIVersion') != 2:
            raise RuntimeError('This app requires ratbagd API version 2.')
        devices = []
        for path in manager.get('Devices', []):
            d = await self.props(path, 'Device')
            if 'g502' not in d.get('Name', '').lower().replace(' ', ''):
                continue
            d['path'] = path
            profiles = []
            for pp in d['Profiles']:
                p = await self.props(pp, 'Profile')
                p['path'] = pp
                for name, kind in [('Resolutions', 'Resolution'), ('Buttons', 'Button')]:
                    entries = []
                    for ep in p[name]:
                        e = await self.props(ep, kind)
                        e['path'] = ep
                        entries.append(e)
                    p[name] = entries
                profiles.append(p)
            d['Profiles'] = profiles
            devices.append(d)
        return devices

    async def change(self, request):
        devices = await self.snapshot()
        d = next((d for d in devices if d['path'] == request['device']), None)
        if not d:
            raise RuntimeError('Mouse disconnected. Reconnect and refresh.')
        p = next(p for p in d['Profiles'] if p['path'] == request['profile'])
        # Do not overwrite another client's pending changes.
        if any(x.get('IsDirty') for x in d['Profiles']):
            raise RuntimeError('Driver has pending changes. Close other mouse tools, restart ratbagd, then refresh.')
        resync = asyncio.Event()
        def signal(msg):
            if msg.path == d['path'] and msg.interface == SERVICE+'.Device' and msg.member == 'Resync':
                resync.set()
        self.bus.add_message_handler(signal)
        rule = f"type='signal',interface='{SERVICE}.Device',member='Resync',path='{d['path']}'"
        reply = await self.bus.call(Message(destination='org.freedesktop.DBus', path='/org/freedesktop/DBus',
            interface='org.freedesktop.DBus', member='AddMatch', signature='s', body=[rule]))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError('Cannot monitor driver write failures.')
        op = request['op']
        if op == 'dpi':
            r = next(r for r in p['Resolutions'] if r['path'] == request['target'])
            dpi = request['dpi']
            if dpi not in r.get('Resolutions', []):
                raise ValueError('DPI is not in the supported values reported by your mouse.')
            current = r['Resolution']
            inner = Variant('(uu)', [dpi, dpi]) if isinstance(current, list) else Variant('u', dpi)
            await self.set(r['path'], 'Resolution', 'Resolution', Variant('v', inner))
            expected = [dpi, dpi] if isinstance(current, list) else dpi
            if (await self.props(r['path'], 'Resolution'))['Resolution'] != expected:
                raise RuntimeError('Driver rejected the DPI value.')
        elif op == 'resolution':
            r = next(r for r in p['Resolutions'] if r['path'] == request['target'])
            if r.get('IsDisabled'):
                raise ValueError('This DPI stage is disabled in the device profile.')
            await self.method(r['path'], 'Resolution', 'SetActive')
        elif op == 'profile':
            if p.get('Disabled'):
                raise ValueError('This profile is disabled in the device.')
            await self.method(p['path'], 'Profile', 'SetActive')
        elif op == 'button':
            b = next(b for b in p['Buttons'] if b['path'] == request['target'])
            kind, value = request['mapping']
            if kind not in b['ActionTypes']:
                raise ValueError('This action type is unsupported on this button.')
            final = [request['mapping'] if x['path'] == b['path'] else x['Mapping'] for x in p['Buttons']]
            if [1, 1] not in final:
                raise ValueError('Keep at least one button assigned to left click.')
            await self.set(b['path'], 'Button', 'Mapping', mapping_variant(kind, value))
            if (await self.props(b['path'], 'Button'))['Mapping'] != [kind, value]:
                raise RuntimeError('Driver rejected the button mapping.')
        else:
            raise ValueError('Unknown operation')
        await self.method(d['path'], 'Device', 'Commit')
        # Commit is asynchronous; wait for dirty flags and listen for Resync failures.
        for _ in range(100):
            await asyncio.sleep(.1)
            if resync.is_set():
                raise RuntimeError('Mouse rejected the write; ratbagd resynchronized its settings.')
            profiles = [await self.props(x['path'], 'Profile') for x in d['Profiles']]
            if not any(x.get('IsDirty', True) for x in profiles):
                break
        else:
            raise RuntimeError('Write did not finish within 10 seconds. Refresh before retrying.')
        fresh = await self.snapshot()
        fd = next(x for x in fresh if x['path'] == d['path'])
        fp = next(x for x in fd['Profiles'] if x['path'] == p['path'])
        if op == 'dpi':
            ok = next(x for x in fp['Resolutions'] if x['path'] == r['path'])['Resolution'] == expected
        elif op == 'button':
            ok = next(x for x in fp['Buttons'] if x['path'] == b['path'])['Mapping'] == [kind, value]
        elif op == 'profile':
            ok = fp['IsActive']
        else:
            ok = next(x for x in fp['Resolutions'] if x['path'] == r['path'])['IsActive']
        if not ok:
            raise RuntimeError('Readback differs from the requested setting. Refresh and inspect diagnostics.')
        return fresh

    async def run(self, request=None):
        self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        try:
            return await (self.change(request) if request else self.snapshot())
        finally:
            self.bus.disconnect()
