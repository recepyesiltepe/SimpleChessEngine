# AppImage (Linux x86_64)

The build bundles **Python 3.11**, **GTK 4**, and **PyGObject** from **conda-forge** into an [AppDir](https://docs.appimage.org/packaging-guide/directory-structure.html), then runs **appimagetool**.

## Requirements

- **Linux x86_64** (build and run target).
- **bash**, **curl**, **tar**, **bzip2**, **base64**.
- **FUSE** on the build machine so `appimagetool` can run (many distros ship `libfuse2`; on Ubuntu you may need `sudo apt install libfuse2`).

## Build

From the repository root:

```bash
chmod +x packaging/appimage/build.sh
./packaging/appimage/build.sh
```

Output: `build/appimage/Simple_Chess_Engine-${VERSION}-x86_64.AppImage` (exact filename depends on appimagetool; check `build/appimage/*.AppImage`).

## Run

```bash
chmod +x ./build/appimage/*.AppImage
./build/appimage/Simple_Chess_Engine-*.AppImage
```

If FUSE is unavailable at runtime, use:

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./Simple_Chess_Engine-*.AppImage
```

## Notes

- **glibc**: Build on the **oldest** distro you need to support; binaries follow the glibc from the build host / conda stack.
- **Size**: The conda prefix is large (GTK + Python); the AppImage compresses most of it. Add `adwaita-icon-theme` to the `micromamba create` line in `build.sh` if you want full system icons in the bundle (increases size).
- **Icon**: `build.sh` drops in a tiny placeholder PNG; replace the base64 block in `packaging/appimage/build.sh` or add a real `simple-chess-engine.png` copy step if you want a branded icon.
