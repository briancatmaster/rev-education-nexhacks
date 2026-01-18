import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables. Please add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to your .env.local file.')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Google OAuth scopes for Drive access
const GOOGLE_DRIVE_SCOPES = [
  'https://www.googleapis.com/auth/drive.readonly',
  'https://www.googleapis.com/auth/drive.metadata.readonly',
]

/**
 * Sign in with Google and request Google Drive permissions
 * Returns the OAuth session with access tokens for Google Drive
 */
export async function signInWithGoogle() {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      scopes: GOOGLE_DRIVE_SCOPES.join(' '),
      queryParams: {
        access_type: 'offline',
        prompt: 'consent',
      },
      redirectTo: `${window.location.origin}/onboarding`,
    },
  })

  if (error) throw error
  return data
}

/**
 * Get the current session with Google tokens
 */
export async function getGoogleSession() {
  const { data: { session }, error } = await supabase.auth.getSession()
  if (error) throw error
  return session
}

/**
 * Get Google Drive access token from current session
 */
export async function getGoogleAccessToken(): Promise<string | null> {
  const session = await getGoogleSession()
  return session?.provider_token || null
}

/**
 * Check if user has Google Drive connected
 */
export async function hasGoogleDriveConnection(userId: number): Promise<boolean> {
  const { data, error } = await supabase
    .from('google_drive_connections')
    .select('id')
    .eq('user_id', userId)
    .eq('is_active', true)
    .single()

  if (error && error.code !== 'PGRST116') {
    console.error('Error checking Google Drive connection:', error)
    return false
  }

  return !!data
}

/**
 * Sign out user
 */
export async function signOut() {
  const { error } = await supabase.auth.signOut()
  if (error) throw error
}

/**
 * Image reference from storage
 */
export interface ImageRef {
  index: number
  path?: string
  url?: string
  page?: number
  width?: number
  height?: number
  alt?: string
  description?: string
  // Legacy format fields
  data?: string
  type?: string
}

/**
 * Material content retrieved from storage
 */
export interface MaterialContent {
  text: string
  image_refs: ImageRef[]
  metadata: {
    material_id: string
    original_tokens: number
    compressed_tokens: number
    compression_ratio: number
    has_figures: boolean
    figure_count: number
    processed_at: string
    format_version: string
  }
}

/**
 * Get processed material content from storage
 * Retrieves compressed text and generates signed URLs for images
 */
export async function getMaterialContent(materialId: string): Promise<MaterialContent | null> {
  // 1. Get material record with storage path
  const { data: material, error: materialError } = await supabase
    .from('academia_materials')
    .select('compressed_storage_path, compressed_storage_bucket, compressed_text, extracted_images')
    .eq('id', materialId)
    .single()

  if (materialError) {
    console.error('Error fetching material:', materialError)
    return null
  }

  if (!material) return null

  // 2. If we have a storage path, download from storage
  if (material.compressed_storage_path && material.compressed_storage_bucket) {
    try {
      const { data: blob, error: downloadError } = await supabase.storage
        .from(material.compressed_storage_bucket)
        .download(material.compressed_storage_path)

      if (downloadError) {
        console.error('Error downloading from storage:', downloadError)
        throw downloadError
      }

      const content: MaterialContent = JSON.parse(await blob.text())

      // 3. Generate signed URLs for images (new format v2.0)
      if (content.image_refs && content.image_refs.length > 0) {
        for (const img of content.image_refs) {
          if (img.path) {
            const { data: signedData, error: signError } = await supabase.storage
              .from(material.compressed_storage_bucket)
              .createSignedUrl(img.path, 3600) // 1 hour expiry

            if (!signError && signedData) {
              img.url = signedData.signedUrl
            } else {
              console.warn(`Failed to create signed URL for ${img.path}:`, signError)
            }
          }
        }
      }

      // Handle legacy format (v1.0) - convert images array to image_refs
      const legacyImages = (content as unknown as { images?: ImageRef[] }).images
      if (legacyImages && legacyImages.length > 0 && (!content.image_refs || content.image_refs.length === 0)) {
        content.image_refs = legacyImages.map(img => ({
          index: img.index,
          url: img.data ? `data:${img.type || 'image/png'};base64,${img.data}` : undefined,
          description: img.description,
          page: img.page,
          width: img.width,
          height: img.height
        }))
      }

      return content
    } catch (e) {
      console.error('Failed to retrieve content from storage:', e)
      // Fall through to legacy data
    }
  }

  // 3. Fallback to inline data for legacy records
  if (material.compressed_text || material.extracted_images) {
    const legacyImages = (material.extracted_images || []) as Array<{
      index: number
      base64: string
      page?: number
      width?: number
      height?: number
      alt?: string
    }>

    return {
      text: material.compressed_text || '',
      image_refs: legacyImages.map(img => ({
        index: img.index,
        url: `data:image/png;base64,${img.base64}`,
        page: img.page,
        width: img.width,
        height: img.height,
        alt: img.alt
      })),
      metadata: {
        material_id: materialId,
        original_tokens: 0,
        compressed_tokens: 0,
        compression_ratio: 1,
        has_figures: legacyImages.length > 0,
        figure_count: legacyImages.length,
        processed_at: '',
        format_version: '1.0'
      }
    }
  }

  return null
}

/**
 * Get multiple materials' content in batch
 */
export async function getMaterialsContent(materialIds: string[]): Promise<Map<string, MaterialContent>> {
  const results = new Map<string, MaterialContent>()

  // Fetch all materials in parallel
  const promises = materialIds.map(async (id) => {
    const content = await getMaterialContent(id)
    if (content) {
      results.set(id, content)
    }
  })

  await Promise.all(promises)
  return results
}
