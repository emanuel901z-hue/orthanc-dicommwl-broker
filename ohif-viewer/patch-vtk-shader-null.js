/**
 * Patch: VTK.js Shader/Context Null-Crash Fix (ALLE Mapper + Helper)
 *
 * Problem 1: TypeError: Cannot read properties of null (reading 'isAttributeUsed')
 *   at setMapperShaderParameters — Shader-Programm ist null
 *
 * Problem 2: TypeError: Cannot read properties of null (reading 'setContext')
 *   at setOpenGLRenderWindow (Helper.js) — model.program ist null
 *   at buildPass (ImageResliceMapper/ImageMapper/VolumeMapper) — triggert Helper-Crash
 *
 * Ursache: WebGL Context Loss, GPU-Memory-Erschoepfung, oder Race-Conditions
 *   beim Viewport-Wechsel. Bekannte Issues: OHIF/Viewers#6010, #2318, Kitware/vtk-js#1814
 *
 * Betroffene Dateien:
 *   - Helper.js (setOpenGLRenderWindow: model.program.setContext crash)
 *   - Glyph3DMapper.js, ImageMapper.js, ImageResliceMapper.js,
 *     PolyDataMapper.js, PolyDataMapper2D.js, SphereMapper.js,
 *     StickMapper.js, VolumeMapper.js
 *
 * Fix Teil 1 (Helper.js): null-check fuer model.program in setOpenGLRenderWindow
 * Fix Teil 2 (alle Mapper): null-check fuer cellBO in setMapperShaderParameters
 * Fix Teil 3 (alle Mapper): try-catch um setMapperShaderParameters/updateShaders Aufrufe
 * Fix Teil 4 (Mapper mit buildPass): null-check fuer _openGLRenderWindow vor tris.setOpenGLRenderWindow
 * Fix Teil 5 (Mapper mit render): null-check fuer _openGLRenderWindow vor primitives[].setOpenGLRenderWindow
 */

const fs = require('fs');
const path = require('path');

const vtkBase = 'node_modules/@kitware/vtk.js/Rendering/OpenGL';
let totalPatches = 0;

// ============================================================
// Teil 1: Helper.js — model.program null-check
// ============================================================
{
  const helperPath = path.join(process.cwd(), vtkBase, 'Helper.js');
  if (fs.existsSync(helperPath)) {
    let src = fs.readFileSync(helperPath, 'utf8');
    if (!src.includes('PATCH_VTK_SHADER_NULL')) {
      // Patch setOpenGLRenderWindow: add null-check for model.program
      // Note: installed vtk.js may use `win =>` or `(win) =>` (with/without parens)
      const helperRegex = /publicAPI\.setOpenGLRenderWindow\s*=\s*\(?\s*win\s*\)?\s*=>\s*\{\s*model\.context\s*=\s*win\.getContext\(\);\s*model\.program\.setContext\(model\.context\);/;
      if (helperRegex.test(src)) {
        src = src.replace(
          helperRegex,
          `publicAPI.setOpenGLRenderWindow = (win) => {
    if (!win) return; // PATCH_VTK_SHADER_NULL: null win guard
    model.context = win.getContext();
    if (!model.context) return; // PATCH_VTK_SHADER_NULL: null context guard
    if (model.program) { model.program.setContext(model.context); } // PATCH_VTK_SHADER_NULL: program null guard`
        );
        fs.writeFileSync(helperPath, src);
        console.log('Helper.js: setOpenGLRenderWindow null-guard (program + context + win)');
        totalPatches += 3;
      } else {
        console.log('Helper.js: WARN - setOpenGLRenderWindow pattern nicht gefunden');
        // Debug: show first 40 lines
        console.log('Helper.js first 35 lines:');
        src.split('\n').slice(0, 35).forEach((l, i) => console.log(`  ${i+1}: ${l}`));
      }
    } else {
      console.log('Helper.js: bereits gepatcht, skip');
    }
  } else {
    console.log('Helper.js: nicht gefunden, skip');
  }
}

// ============================================================
// Teil 2-5: Alle Mapper patchen
// ============================================================
const mapperFiles = [
  'Glyph3DMapper.js',
  'ImageMapper.js',
  'ImageResliceMapper.js',
  'PolyDataMapper.js',
  'PolyDataMapper2D.js',
  'SphereMapper.js',
  'StickMapper.js',
  'VolumeMapper.js',
];

for (const mapperFile of mapperFiles) {
  const fullPath = path.join(process.cwd(), vtkBase, mapperFile);
  if (!fs.existsSync(fullPath)) {
    console.log(`${mapperFile}: nicht gefunden, skip`);
    continue;
  }

  let src = fs.readFileSync(fullPath, 'utf8');

  if (src.includes('PATCH_VTK_SHADER_NULL')) {
    console.log(`${mapperFile}: bereits gepatcht, skip`);
    continue;
  }

  let patchCount = 0;

  // Teil 2: setMapperShaderParameters - null guard for cellBO parameter
  const setMapperRegex = /publicAPI\.setMapperShaderParameters\s*=\s*\(([^)]*)\)\s*=>\s*\{/;
  const setMapperMatch = src.match(setMapperRegex);
  if (setMapperMatch) {
    const params = setMapperMatch[1];
    const firstParam = params.split(',')[0].trim();
    if (firstParam) {
      const guard = `if (!${firstParam} || !${firstParam}.getProgram || !${firstParam}.getProgram()) return; // PATCH_VTK_SHADER_NULL`;
      src = src.replace(
        setMapperRegex,
        `publicAPI.setMapperShaderParameters = (${params}) => {\n    ${guard}`
      );
      patchCount++;
      console.log(`${mapperFile}: setMapperShaderParameters null-guard (param: ${firstParam})`);
    }
  }

  // Teil 3a: updateShaders - wrap setMapperShaderParameters call in try-catch
  const callPattern = /(\w+)\.setMapperShaderParameters\((\w+),\s*(\w+),\s*(\w+)\);/g;
  let replaced;
  while ((replaced = callPattern.exec(src)) !== null) {
    const beforeCall = src.substring(Math.max(0, replaced.index - 20), replaced.index);
    if (beforeCall.includes('= (') || beforeCall.includes('=>')) continue;

    const origCall = replaced[0];
    const tryCatchCall = `try { ${origCall} } catch (e) { /* PATCH_VTK_SHADER_NULL */ }`;
    src = src.substring(0, replaced.index) + tryCatchCall + src.substring(replaced.index + origCall.length);
    patchCount++;
    console.log(`${mapperFile}: try-catch um setMapperShaderParameters call`);
    callPattern.lastIndex = replaced.index + tryCatchCall.length;
  }

  // Teil 3b: renderPieceDraw - wrap updateShaders call in try-catch
  const updateCallPattern = /(\w+)\.updateShaders\(([^)]+)\);/g;
  let replaced2;
  while ((replaced2 = updateCallPattern.exec(src)) !== null) {
    const beforeCall2 = src.substring(Math.max(0, replaced2.index - 20), replaced2.index);
    if (beforeCall2.includes('= (') || beforeCall2.includes('=>')) continue;
    const afterCall = src.substring(replaced2.index + replaced2[0].length, replaced2.index + replaced2[0].length + 10);
    if (afterCall.includes('} catch')) continue;

    const origCall2 = replaced2[0];
    const tryCatchCall2 = `try { ${origCall2} } catch (e) { /* PATCH_VTK_SHADER_NULL */ }`;
    src = src.substring(0, replaced2.index) + tryCatchCall2 + src.substring(replaced2.index + origCall2.length);
    patchCount++;
    console.log(`${mapperFile}: try-catch um updateShaders call`);
    updateCallPattern.lastIndex = replaced2.index + tryCatchCall2.length;
  }

  // Teil 4: buildPass - null-check for _openGLRenderWindow before tris.setOpenGLRenderWindow
  // Pattern: model.tris.setOpenGLRenderWindow(model._openGLRenderWindow);
  const trisPattern = /model\.tris\.setOpenGLRenderWindow\(model\._openGLRenderWindow\);/g;
  let replaced3;
  while ((replaced3 = trisPattern.exec(src)) !== null) {
    const origCall3 = replaced3[0];
    const guardedCall3 = `if (model._openGLRenderWindow && model.tris) { ${origCall3} } // PATCH_VTK_SHADER_NULL`;
    src = src.substring(0, replaced3.index) + guardedCall3 + src.substring(replaced3.index + origCall3.length);
    patchCount++;
    console.log(`${mapperFile}: null-guard um tris.setOpenGLRenderWindow`);
    trisPattern.lastIndex = replaced3.index + guardedCall3.length;
  }

  // Teil 5: render() - null-check for _openGLRenderWindow before primitives[].setOpenGLRenderWindow
  // Pattern: model.primitives[i].setOpenGLRenderWindow(model._openGLRenderWindow);
  const primPattern = /model\.primitives\[i\]\.setOpenGLRenderWindow\(model\._openGLRenderWindow\);/g;
  let replaced4;
  while ((replaced4 = primPattern.exec(src)) !== null) {
    const origCall4 = replaced4[0];
    const guardedCall4 = `if (model._openGLRenderWindow && model.primitives[i]) { ${origCall4} } // PATCH_VTK_SHADER_NULL`;
    src = src.substring(0, replaced4.index) + guardedCall4 + src.substring(replaced4.index + origCall4.length);
    patchCount++;
    console.log(`${mapperFile}: null-guard um primitives[i].setOpenGLRenderWindow`);
    primPattern.lastIndex = replaced4.index + guardedCall4.length;
  }

  // Teil 5b: render() - null-check for _openGLRenderWindow.getContext() call
  // Pattern: const ctx = model._openGLRenderWindow.getContext();
  const ctxPattern = /const ctx = model\._openGLRenderWindow\.getContext\(\);/g;
  let replaced5;
  while ((replaced5 = ctxPattern.exec(src)) !== null) {
    const origCall5 = replaced5[0];
    const guardedCall5 = `const ctx = model._openGLRenderWindow ? model._openGLRenderWindow.getContext() : null; if (!ctx) return; // PATCH_VTK_SHADER_NULL`;
    src = src.substring(0, replaced5.index) + guardedCall5 + src.substring(replaced5.index + origCall5.length);
    patchCount++;
    console.log(`${mapperFile}: null-guard um _openGLRenderWindow.getContext()`);
    ctxPattern.lastIndex = replaced5.index + guardedCall5.length;
  }

  // Teil 5c: buildPass - null-check for _openGLRenderWindow.getContext() in buildPass
  // Pattern: model.context = model._openGLRenderWindow.getContext();
  const buildCtxPattern = /model\.context = model\._openGLRenderWindow\.getContext\(\);/g;
  let replaced6;
  while ((replaced6 = buildCtxPattern.exec(src)) !== null) {
    const origCall6 = replaced6[0];
    const guardedCall6 = `if (!model._openGLRenderWindow) return; model.context = model._openGLRenderWindow.getContext(); if (!model.context) return; // PATCH_VTK_SHADER_NULL`;
    src = src.substring(0, replaced6.index) + guardedCall6 + src.substring(replaced6.index + origCall6.length);
    patchCount++;
    console.log(`${mapperFile}: null-guard um buildPass getContext()`);
    buildCtxPattern.lastIndex = replaced6.index + guardedCall6.length;
  }

  if (patchCount > 0) {
    fs.writeFileSync(fullPath, src);
    console.log(`${mapperFile}: ${patchCount} Patch(es) angewendet`);
    totalPatches += patchCount;
  } else {
    console.log(`${mapperFile}: keine passenden Stellen gefunden`);
  }
}

console.log(`\nGesamt: ${totalPatches} Patch(es) in allen Dateien`);
