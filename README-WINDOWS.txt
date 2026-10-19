Lightpanda - native Windows x64 build
=====================================

Contents
  lightpanda.exe         the browser
  VCRUNTIME140*.dll      Microsoft Visual C++ runtime used by V8
  LICENSE                AGPL-3.0

Usage
  lightpanda.exe fetch --dump markdown https://example.com
  lightpanda.exe serve --host 127.0.0.1 --port 9222

Keep the CDP server on 127.0.0.1. Anyone who can reach the port can
drive the browser.

Built from https://github.com/Amor216/browser (branch windows-port), a
fork of https://github.com/lightpanda-io/browser with the native Windows
port from lightpanda-io/browser#3753 and lightpanda-io/zig-v8-fork#219.

Known limits of the Windows port
  - Unix-domain sockets (serve --unix-socket) are not supported.
  - V8 is built without Control Flow Guard (it clashes with the mingw CRT).
