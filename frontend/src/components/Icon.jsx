const SIZES = {
  sm: 16,
  md: 24,
  lg: 32,
}

// Inline paths so icons need no sprite fetch and inherit currentColor.
const PATHS = {
  'bookmark-outline': (
    <path
      d="M6 4h12a1 1 0 0 1 1 1v15l-7-4-7 4V5a1 1 0 0 1 1-1Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  ),
  'bookmark-filled': (
    <path
      d="M6 4h12a1 1 0 0 1 1 1v15l-7-4-7 4V5a1 1 0 0 1 1-1Z"
      fill="currentColor"
    />
  ),
}

function Icon({ name, size = 'md' }) {
  const px = SIZES[size]
  return (
    <svg
      className="icon"
      width={px}
      height={px}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  )
}

export default Icon
