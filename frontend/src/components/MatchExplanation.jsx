import Markdown from 'react-markdown'

/**
 * Renders the ranker's Markdown explanation.
 *
 * This string is model output, so it is untrusted input that happens to look
 * like content. Two rules follow:
 *
 * 1. Never dangerouslySetInnerHTML. react-markdown escapes by default and does
 *    not render raw HTML without an explicit rehype-raw plugin — which is the
 *    whole reason for taking the dependency instead of regexing `**bold**`.
 * 2. Block elements get flattened. The prompt asks for "short Markdown", but
 *    nothing enforces it: a model that decides to emit an `<h1>` or a nested
 *    list must not be able to restructure a result card.
 */

const Bold = ({ children }) => <strong>{children}</strong>

const COMPONENTS = {
  // A stray heading becomes bold text rather than a layout-breaking block.
  h1: Bold,
  h2: Bold,
  h3: Bold,
  h4: Bold,
  h5: Bold,
  h6: Bold,

  p: ({ children }) => <p className="match-explanation-p">{children}</p>,
  ul: ({ children }) => <ul className="match-explanation-list">{children}</ul>,
  ol: ({ children }) => <ol className="match-explanation-list">{children}</ol>,
  code: ({ children }) => <code className="match-explanation-code">{children}</code>,

  // Keep the link text, drop the href. A model-authored URL inside a lending
  // recommendation has no legitimate purpose and is a ready-made phishing
  // surface — the user would have every reason to trust it.
  a: ({ children }) => <span>{children}</span>,

  // Same reasoning: a remote image in an explanation is a tracking pixel at
  // best, and the model has no image worth showing here.
  img: () => null,

  // Blockquotes and rules add vertical noise to a card for no information.
  blockquote: ({ children }) => <span>{children}</span>,
  hr: () => null,
}

function MatchExplanation({ text }) {
  if (!text) return null
  return (
    <div className="match-explanation">
      <Markdown components={COMPONENTS}>{text}</Markdown>
    </div>
  )
}

export default MatchExplanation
