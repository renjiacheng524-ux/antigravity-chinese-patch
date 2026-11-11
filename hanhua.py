# -*- coding: utf-8 -*-
"""
Antigravity 一键汉化（版本无关，官方 asar 工具打包）

流程：解包当前 app.asar → 把 engine.js 注入 preload.js / wizardPreload.js
      → 官方工具重新打包（保留 unpacked 结构）→ 备份 → 替换

用法： python hanhua.py            # 执行（汉化并启动）
      python hanhua.py patch      # 执行，但不自动启动（给更新后的自愈启动器用）
      python hanhua.py check      # 只检查：已汉化 exit 0，未汉化 exit 2
      python hanhua.py --dry-run  # 只打包到 _new.asar，不杀进程、不替换、不启动
"""
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ASAR = os.path.expandvars(
    r'%LOCALAPPDATA%\Programs\Antigravity\resources\app.asar')
ENGINE = os.path.join(HERE, 'engine.js')
ASAR_CLI = os.path.join(HERE, 'node_modules', '@electron', 'asar', 'bin', 'asar.mjs')
TMP = os.path.join(HERE, '_build')
MARK = 'Chinese Localization Engine'
UNPACK_DIR = 'node_modules/chrome-devtools-mcp'
TARGETS = ['dist/preload.js', 'dist/ideInstall/wizardPreload.js']


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', **kw)


def is_hans():
    sys.path.insert(0, HERE)
    import asar_lib
    try:
        for m in TARGETS:
            d = asar_lib.extract(ASAR, m, os.path.join(TMP, '_chk.js'))
            if d < 0:
                continue
            if MARK in open(os.path.join(TMP, '_chk.js'),
                            encoding='utf-8', errors='replace').read():
                return True
    except Exception:
        pass
    return False


def main():
    mode = 'apply'
    debug_port = ''
    dry_run = False
    for a in sys.argv[1:]:
        if a == '--dry-run':
            dry_run = True
        elif a.startswith('--debug-port='):
            debug_port = a.split('=', 1)[1]
        elif not a.startswith('-'):
            mode = a

    if not os.path.exists(ASAR):
        print('!! 找不到 Antigravity:', ASAR)
        return 1
    if not os.path.exists(ENGINE):
        print('!! 缺少 engine.js')
        return 1

    if mode == 'check':
        hans = is_hans()
        print('已汉化' if hans else '未汉化（官方原版）')
        # 退出码给启动器用：0 = 已汉化，2 = 需要重新汉化
        return 0 if hans else 2

    # 关掉 Antigravity，否则文件被占用（dry-run 不动进程）
    if not dry_run:
        for img in ('Antigravity.exe', 'language_server.exe'):
            run(['taskkill', '/F', '/IM', img])
        time.sleep(3)

    engine = open(ENGINE, encoding='utf-8').read().strip('\n')
    print(f'引擎 {len(engine):,} 字符')

    # 解包
    shutil.rmtree(TMP, ignore_errors=True)
    print('解包中 ...')
    r = run(['node', ASAR_CLI, 'extract', ASAR, TMP])
    if not os.path.isdir(TMP):
        print('!! 解包失败', (r.stderr or '')[:300])
        return 1

    # 注入
    done = 0
    for m in TARGETS:
        p = os.path.join(TMP, m.replace('/', os.sep))
        if not os.path.exists(p):
            print(f'  跳过（本版无此文件）: {m}')
            continue
        txt = open(p, encoding='utf-8').read()
        marker = '// ' + MARK + ' Enhanced'
        if MARK in txt:
            # 已注入过旧引擎：先剥离，再写入最新引擎（支持引擎升级）
            cut = txt.find(marker)
            if cut < 0:
                cut = txt.find('// ' + MARK)
            if cut < 0:
                cut = txt.find(MARK)
            txt = txt[:cut].rstrip('\n') if cut >= 0 else txt
            print(f'  刷新引擎: {m}')
        txt = txt.rstrip('\n') + '\n\n' + marker + '\n' + engine + '\n'
        open(p, 'w', encoding='utf-8', newline='\n').write(txt)
        print(f'  注入: {m}  -> {len(txt.encode()):,} bytes')
        done += 1

    if not done:
        print('!! 没有可注入的文件')
        return 1

    # 打包
    out = os.path.join(HERE, '_new.asar')
    if os.path.exists(out):
        os.remove(out)
    print('打包中 ...')
    r = run(['node', ASAR_CLI, 'pack', TMP, out, '--unpack-dir', UNPACK_DIR])
    if not os.path.exists(out):
        print('!! 打包失败', (r.stderr or '')[:400])
        return 1

    # 语法自检
    chk = run(['node', '--check', os.path.join(TMP, 'dist', 'preload.js')])
    if chk.returncode != 0:
        print('!! preload 语法检查失败，已中止：')
        print((chk.stderr or '')[:400])
        return 1

    size = os.path.getsize(out)
    print(f'新包 {size:,} bytes')

    if dry_run:
        print(f'[DRY-RUN] 打包成功，未替换 {ASAR}')
        return 0

    # 备份 + 替换
    bak = ASAR + '.bak-' + time.strftime('%Y%m%d-%H%M%S')
    shutil.copy2(ASAR, bak)
    shutil.copy2(out, ASAR)
    print(f'原版备份: {bak}')
    print(f'[OK] 汉化完成: {ASAR}')

    # patch 模式：只汉化，启动交给调用方（自愈启动器）
    if mode == 'patch':
        return 0

    # 启动（带代理，避免 language_server 连不上 Google 卡 77 秒）
    if debug_port:
        exe = os.path.join(os.environ['LOCALAPPDATA'], 'Programs', 'Antigravity',
                           'Antigravity.exe')
        env = os.environ.copy()
        for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy'):
            env[k] = 'http://127.0.0.1:7897'
        env['NO_PROXY'] = env['no_proxy'] = '127.0.0.1,localhost,::1'
        env.pop('ELECTRON_RUN_AS_NODE', None)
        env.pop('NODE_OPTIONS', None)
        subprocess.Popen([
            exe,
            f'--remote-debugging-port={debug_port}',
            '--proxy-server=http://127.0.0.1:7897',
            '--proxy-bypass-list=127.0.0.1;localhost;<local>',
        ], env=env, close_fds=True)
        print(f'已启动 Antigravity（调试端口 {debug_port}）')
        return 0

    vbs = os.path.join(HERE, 'launch_antigravity.vbs')
    if os.path.exists(vbs):
        run(['wscript.exe', '//B', '//Nologo', vbs])
        print('已启动 Antigravity')
    return 0


if __name__ == '__main__':
    sys.exit(main())
