import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import client from '../api/client'
import Button from '../components/Button'

// Must match the backend Listing.Category / Listing.Condition TextChoices.
const CATEGORIES = [
  'tools',
  'appliances',
  'electronics',
  'furniture',
  'sporting_goods',
  'other',
]
const CONDITIONS = ['new', 'like_new', 'good', 'fair', 'poor']

function CreateListingForm() {
  const navigate = useNavigate()

  // Phase 1 — input
  const [image, setImage] = useState(null)
  const [description, setDescription] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [extractError, setExtractError] = useState(null)

  // Phase 2 — editable draft returned by extraction
  const [draft, setDraft] = useState(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState(null)

  async function handleExtract(event) {
    event.preventDefault()
    setExtractError(null)
    if (!image) {
      setExtractError('Please choose a photo first.')
      return
    }
    setExtracting(true)
    try {
      const form = new FormData()
      form.append('image', image)
      form.append('description', description)
      // axios sets the multipart boundary automatically for FormData bodies.
      const { data } = await client.post('/listings/extract/', form)
      // Map the extraction into an editable draft. suggested_price -> price;
      // latitude/longitude aren't extracted, so the lender fills those in.
      setDraft({
        title: data.title ?? '',
        description: data.description ?? '',
        category: data.category ?? 'other',
        condition: data.condition ?? 'good',
        price: data.suggested_price ?? '',
        latitude: '',
        longitude: '',
      })
    } catch {
      setExtractError(
        'Could not read the photo. Try again, or fill the form in manually.',
      )
    } finally {
      setExtracting(false)
    }
  }

  function updateField(field, value) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  async function handleCreate(event) {
    event.preventDefault()
    setCreateError(null)
    setCreating(true)
    try {
      await client.post('/listings/', {
        title: draft.title,
        description: draft.description,
        category: draft.category,
        condition: draft.condition,
        price: draft.price,
        latitude: parseFloat(draft.latitude),
        longitude: parseFloat(draft.longitude),
      })
      navigate('/')
    } catch {
      setCreateError(
        'Could not create the listing. Check the fields and try again.',
      )
    } finally {
      setCreating(false)
    }
  }

  // Phase 1: pick a photo + describe, then extract.
  if (!draft) {
    return (
      <form onSubmit={handleExtract}>
        <h2>New Listing</h2>
        <div>
          <input
            type="file"
            accept="image/*"
            onChange={(event) => setImage(event.target.files[0])}
          />
        </div>
        <div>
          <textarea
            placeholder="Describe the item (optional — helps the extraction)"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
        {extractError && <p style={{ color: 'crimson' }}>{extractError}</p>}
        <Button type="submit" disabled={extracting}>
          {extracting
            ? 'Reading the photo… this can take a few seconds'
            : 'Extract details'}
        </Button>
      </form>
    )
  }

  // Phase 2: review + edit the extracted fields, then create for real.
  return (
    <form onSubmit={handleCreate}>
      <h2>Review &amp; edit</h2>
      <label>
        Title
        <input
          value={draft.title}
          onChange={(event) => updateField('title', event.target.value)}
        />
      </label>
      <label>
        Description
        <textarea
          value={draft.description}
          onChange={(event) => updateField('description', event.target.value)}
        />
      </label>
      <label>
        Category
        <select
          value={draft.category}
          onChange={(event) => updateField('category', event.target.value)}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <label>
        Condition
        <select
          value={draft.condition}
          onChange={(event) => updateField('condition', event.target.value)}
        >
          {CONDITIONS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <label>
        Price
        <input
          value={draft.price}
          onChange={(event) => updateField('price', event.target.value)}
        />
      </label>
      <label>
        Latitude
        <input
          value={draft.latitude}
          onChange={(event) => updateField('latitude', event.target.value)}
        />
      </label>
      <label>
        Longitude
        <input
          value={draft.longitude}
          onChange={(event) => updateField('longitude', event.target.value)}
        />
      </label>
      {createError && <p style={{ color: 'crimson' }}>{createError}</p>}
      <Button type="submit" disabled={creating}>
        {creating ? 'Creating…' : 'Confirm & create listing'}
      </Button>
    </form>
  )
}

export default CreateListingForm
