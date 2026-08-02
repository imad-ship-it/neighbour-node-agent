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
  bell: (
    <path
      d="M12 3a5 5 0 0 0-5 5v3.5L5.5 15h13L17 11.5V8a5 5 0 0 0-5-5Zm-2 14a2 2 0 0 0 4 0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  ),
  // Per-kind icons for the notification dropdown. A message and a match are
  // different events and should not look identical in a list.
  message: (
    <path
      d="M4 5h16v11H9l-4 3.5V16H4V5Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  ),
  spark: (
    <path
      d="M12 3.5 13.9 9l5.6 1.9-5.6 1.9L12 18.4l-1.9-5.6L4.5 11 10.1 9 12 3.5Z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
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
