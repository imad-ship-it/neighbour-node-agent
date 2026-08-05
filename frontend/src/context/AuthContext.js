import { createContext } from 'react'

// The context object lives alone in this file, apart from both the provider that
// fills it and the hook that reads it.
//
// That split is a lint constraint, not a stylistic one. `react-refresh` requires
// a module to export components or non-components, never both — mixing them
// breaks Fast Refresh, because the bundler cannot tell whether a changed export
// can be hot-swapped or needs a full remount. A single file holding the context,
// the provider and the hook exports all three kinds at once.
export const AuthContext = createContext(null)
