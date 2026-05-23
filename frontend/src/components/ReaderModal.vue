<template>
  <Teleport to="body">
    <div v-if="currentItem"
         class="reader-overlay"
         @click.self="reader.close()"
         :style="{ '--reader-font-size': fontSize + 'px' }">
      <article class="reader-panel" role="dialog" aria-modal="true"
               :aria-labelledby="'reader-title-' + (currentItem.id || 'x')">
        <!-- Sticky header: title + font controls + close -->
        <header class="reader-header">
          <div class="reader-title-block">
            <p class="reader-eyebrow">{{ currentItem.artista || 'Artista' }}</p>
            <h2 :id="'reader-title-' + (currentItem.id || 'x')" class="reader-title">
              {{ currentItem.titulo }}
              <span v-if="currentItem.tipo" class="reader-tipo"> · {{ currentItem.tipo }}</span>
            </h2>
          </div>
          <div class="reader-controls">
            <button type="button" @click="reader.decFont()"
                    :disabled="!reader.canDecrease()"
                    class="reader-btn-icon" aria-label="Diminuir fonte">A−</button>
            <span class="reader-font-readout">{{ fontSize }}</span>
            <button type="button" @click="reader.incFont()"
                    :disabled="!reader.canIncrease()"
                    class="reader-btn-icon" aria-label="Aumentar fonte">A+</button>
            <button type="button" ref="closeBtn" @click="reader.close()"
                    class="reader-btn-close" aria-label="Fechar">×</button>
          </div>
        </header>

        <!-- Body: editorial text sections only — no poster, no links, no fontes -->
        <div class="reader-body">
          <!-- selo badges (estreia / awards) -->
          <div v-if="currentItem.is_estreia || (currentItem.selos_editoriais && currentItem.selos_editoriais.length)"
               class="reader-badges">
            <span v-if="currentItem.is_estreia" class="reader-badge reader-badge-estreia">✨ ESTREIA</span>
            <span v-for="s in (currentItem.selos_editoriais || [])" :key="s.fonte + s.tipo" class="reader-badge">
              🏅 {{ s.fonte }}: {{ s.tipo }}{{ s.nota ? ' ' + s.nota : '' }}
            </span>
          </div>

          <!-- Text fields, mirroring ReleaseCard reading order -->
          <section v-for="f in textFields" :key="f.key" v-show="currentItem[f.key]">
            <p class="reader-section-label">{{ f.label }}</p>
            <p class="reader-section-body">{{ currentItem[f.key] }}</p>
          </section>

          <!-- "Parecido com" as a list -->
          <section v-if="currentItem.parecido_com && currentItem.parecido_com.length">
            <p class="reader-section-label">Parecido com</p>
            <ul class="reader-list">
              <li v-for="p in currentItem.parecido_com" :key="p" class="reader-section-body">{{ p }}</li>
            </ul>
          </section>

          <!-- Citação destacada -->
          <blockquote v-if="currentItem.citacao_destacada" class="reader-quote">
            <p class="reader-quote-text">"{{ currentItem.citacao_destacada.texto }}"</p>
            <footer class="reader-quote-attrib">
              {{ currentItem.citacao_destacada.fonte
              }}<span v-if="currentItem.citacao_destacada.nota"> · {{ currentItem.citacao_destacada.nota }}</span>
            </footer>
          </blockquote>

          <!-- Verso destacado -->
          <blockquote v-if="currentItem.verso_destacado" class="reader-quote reader-quote-verse">
            <p class="reader-quote-text">"{{ currentItem.verso_destacado.texto }}"</p>
            <footer v-if="currentItem.verso_destacado.faixa" class="reader-quote-attrib">
              faixa "{{ currentItem.verso_destacado.faixa }}"
            </footer>
          </blockquote>

          <!-- O que não esperar (warning box) -->
          <section v-if="currentItem.o_que_nao_esperar" class="reader-warn">
            <p class="reader-section-label">⚠ O que não esperar</p>
            <p class="reader-section-body">{{ currentItem.o_que_nao_esperar }}</p>
          </section>

          <!-- Vale pra você (closing emphasis) -->
          <section v-if="currentItem.vale_pra_voce" class="reader-conclusion">
            <p class="reader-section-label">Vale pra você</p>
            <p class="reader-section-body">{{ currentItem.vale_pra_voce }}</p>
          </section>
        </div>
      </article>
    </div>
  </Teleport>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue"
import { useReader } from "../composables/useReader.js"

const reader = useReader()
const { currentItem, fontSize } = reader
const closeBtn = ref(null)

// Editorial text fields shown in the same order ReleaseCard uses them.
const textFields = [
  { key: 'resumo_critica',     label: 'A crítica' },
  { key: 'na_discografia',     label: 'Na discografia' },
  { key: 'letra_fala_sobre',   label: 'As letras' },
  { key: 'mudanca_musical',    label: 'O que muda' },
  { key: 'para_quem_gosta_de', label: 'Pra quem curte' },
  { key: 'prestar_atencao',    label: 'Preste atenção' },
  { key: 'dados_curiosos',     label: 'Bastidores' },
]

function onKey(e) { if (e.key === "Escape") reader.close() }

// When a card opens: lock background scroll, wire Esc, focus close button.
// On close OR unmount: undo everything. Defense in depth on unmount in case
// the component is torn down while the modal is open.
watch(currentItem, async (it) => {
  if (it) {
    document.body.style.overflow = "hidden"
    document.addEventListener("keydown", onKey)
    await nextTick()
    closeBtn.value?.focus()
  } else {
    document.body.style.overflow = ""
    document.removeEventListener("keydown", onKey)
  }
})
onBeforeUnmount(() => {
  document.body.style.overflow = ""
  document.removeEventListener("keydown", onKey)
})
</script>

<style scoped>
.reader-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(0,0,0,0.75);
  display: flex; align-items: flex-start; justify-content: center;
  overflow-y: auto;
}
.reader-panel {
  background: #fff;
  width: 100%;
  max-width: 720px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
@media (min-width: 640px) {
  .reader-overlay { padding: 2rem 1rem; }
  .reader-panel {
    min-height: auto;
    max-height: calc(100vh - 4rem);
    border-radius: .5rem;
    box-shadow: 0 10px 40px rgba(0,0,0,.4);
    overflow: hidden;
  }
}

/* ── Header ─────────────────────────────────────── */
.reader-header {
  position: sticky; top: 0; z-index: 2;
  display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;
  background: #fff;
  border-bottom: 1px solid #e7e5e4;
  padding: .9rem 1rem;
}
.reader-title-block { min-width: 0; flex: 1; }
.reader-eyebrow {
  font-size: 10px; text-transform: uppercase; letter-spacing: .13em;
  color: #a8a29e; font-weight: 600; margin: 0 0 2px;
}
.reader-title {
  font-family: Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif;
  font-size: 1.15rem; font-weight: 700; color: #1c1917; line-height: 1.25;
  margin: 0;
}
.reader-tipo { font-weight: 400; color: #78716c; font-size: 0.85em; }

.reader-controls { display: flex; align-items: center; gap: .25rem; flex-shrink: 0; }
.reader-btn-icon, .reader-btn-close {
  min-width: 36px; min-height: 36px;
  display: inline-flex; align-items: center; justify-content: center;
  background: #fafaf9; border: 1px solid #e7e5e4; color: #44403c;
  font-weight: 600; font-size: 13px; border-radius: 6px;
  cursor: pointer;
}
.reader-btn-icon:disabled { opacity: .35; cursor: not-allowed; }
.reader-btn-close { font-size: 20px; padding-bottom: 2px; }
.reader-font-readout {
  font-size: 11px; color: #78716c; min-width: 22px; text-align: center;
  font-variant-numeric: tabular-nums;
}

/* ── Body ─────────────────────────────────────── */
.reader-body {
  flex: 1; overflow-y: auto;
  padding: 1.25rem 1.25rem 2.5rem;
  font-family: Charter, "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif;
  font-size: var(--reader-font-size, 22px);
  line-height: 1.8;
  color: #44403c;
}
.reader-body > * + * { margin-top: 1.5em; }

/* Labels scale WITH the body — em-relative, not px-fixed */
.reader-section-label {
  font-size: 0.55em;
  text-transform: uppercase;
  letter-spacing: 0.13em;
  font-weight: 600;
  color: #92400e;
  margin: 0 0 .35em;
}
.reader-section-body { margin: 0; }

.reader-list { margin: 0; padding-left: 0; list-style: none; }
.reader-list li {
  padding-left: .8em;
  border-left: 2px solid #e7e5e4;
  margin-top: .55em;
}
.reader-list li:first-child { margin-top: 0; }

/* Badges (estreia, selos editoriais) */
.reader-badges { display: flex; flex-wrap: wrap; gap: .4em; }
.reader-badge {
  font-size: 0.5em; font-weight: 600; text-transform: uppercase;
  letter-spacing: .04em;
  padding: .35em .8em;
  border-radius: 9999px;
  background: #f5f5f4; border: 1px solid #e7e5e4; color: #44403c;
}
.reader-badge-estreia { background: #ede9fe; border-color: #ddd6fe; color: #4c1d95; }

/* Quotes */
.reader-quote {
  margin: 0; padding-left: 1em;
  border-left: 3px solid #fcd34d;
  background: rgba(254, 243, 199, 0.35);
  padding: 1em 1em 1em 1.15em;
  border-radius: 0 .35em .35em 0;
}
.reader-quote-verse {
  border-left-color: #d6d3d1;
  background: transparent;
  padding: .5em 0 .5em 1.15em;
  border-radius: 0;
}
.reader-quote-text { font-style: italic; margin: 0; }
.reader-quote-attrib {
  font-size: 0.45em; text-transform: uppercase; letter-spacing: .1em;
  color: #92400e; margin-top: .8em;
}
.reader-quote-verse .reader-quote-attrib { color: #a8a29e; }

/* Warn box (o que não esperar) */
.reader-warn {
  background: #fef3c7; border: 1px solid #fde68a;
  border-radius: .35em; padding: .9em 1em;
}
.reader-warn .reader-section-label { color: #92400e; }

/* Closing emphasis (vale pra você) */
.reader-conclusion {
  border-top: 1px solid #e7e5e4;
  padding-top: 1em;
  color: #1c1917;
}
</style>
