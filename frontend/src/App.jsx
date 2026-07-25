import { Routes, Route } from 'react-router-dom'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Listings from './pages/Listings'
import CreateListingForm from './pages/CreateListingForm'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Listings />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/create" element={<CreateListingForm />} />
    </Routes>
  )
}

export default App
