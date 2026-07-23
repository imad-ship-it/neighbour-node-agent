const SIZES = {
  sm: 16,
  md: 24,
  lg: 32,
}

function Icon({ name, size = 'md' }) {
  const px = SIZES[size]
  return (
    <span
      className="icon"
      style={{ width: px, height: px, display: 'inline-block' }}
      data-icon={name}
    />
  )
}

export default Icon
