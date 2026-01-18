export type MaterialType =
  | 'url'
  | 'description'
  | 'cv'
  | 'paper_read'
  | 'paper_written'
  | 'educational_material_practiced'
  | 'educational_material_engaged'
  | 'notes'
  | 'completed_problems'

export interface StudentMaterial {
  id: string
  type: MaterialType
  url: string | null
  storage_bucket_link: string | null
  created_at: string
  updated_at: string
}

export interface CreateStudentMaterial {
  type: MaterialType
  url?: string | null
  storage_bucket_link?: string | null
}

export interface UpdateStudentMaterial {
  type?: MaterialType
  url?: string | null
  storage_bucket_link?: string | null
}

/**
 * Generates the storage path for a material file
 * @param type - The material type
 * @param id - The material ID
 * @returns The storage path following the naming convention: {type}.{id}
 */
export function getStoragePath(type: MaterialType, id: string): string {
  return `${type}.${id}`
}

/**
 * Parses a storage path into type and id
 * @param path - The storage path (e.g., "cv.123e4567-e89b-12d3-a456-426614174000")
 * @returns Object with type and id, or null if invalid format
 */
export function parseStoragePath(path: string): { type: MaterialType; id: string } | null {
  const parts = path.split('.')
  if (parts.length < 2) return null

  const type = parts[0] as MaterialType
  const id = parts.slice(1).join('.')

  return { type, id }
}
