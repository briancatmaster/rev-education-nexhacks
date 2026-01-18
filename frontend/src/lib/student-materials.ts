import { supabase, STUDENT_MATERIALS_BUCKET } from './supabase'
import type {
  StudentMaterial,
  CreateStudentMaterial,
  UpdateStudentMaterial,
  MaterialType,
} from './supabase-types'
import { getStoragePath } from './supabase-types'

/**
 * Creates a new student material record
 */
export async function createStudentMaterial(
  data: CreateStudentMaterial
): Promise<{ data: StudentMaterial | null; error: Error | null }> {
  const { data: material, error } = await supabase
    .from('student_materials')
    .insert(data)
    .select()
    .single()

  return {
    data: material as StudentMaterial | null,
    error: error ? new Error(error.message) : null,
  }
}

/**
 * Uploads a file to the storage bucket and creates/updates the material record
 * @param type - The material type
 * @param file - The file to upload
 * @param materialId - Optional existing material ID to update
 * @returns The created/updated material record
 */
export async function uploadStudentMaterial(
  type: MaterialType,
  file: File,
  materialId?: string
): Promise<{ data: StudentMaterial | null; error: Error | null }> {
  try {
    let material: StudentMaterial

    // Create or use existing material record
    if (materialId) {
      const { data: existingMaterial, error: fetchError } = await supabase
        .from('student_materials')
        .select()
        .eq('id', materialId)
        .single()

      if (fetchError) throw new Error(fetchError.message)
      material = existingMaterial as StudentMaterial
    } else {
      const { data: newMaterial, error: createError } = await createStudentMaterial({ type })
      if (createError || !newMaterial) throw createError || new Error('Failed to create material')
      material = newMaterial
    }

    // Upload file to storage with naming convention
    const storagePath = getStoragePath(type, material.id)
    const { error: uploadError } = await supabase.storage
      .from(STUDENT_MATERIALS_BUCKET)
      .upload(storagePath, file, {
        upsert: true,
      })

    if (uploadError) throw new Error(uploadError.message)

    // Update material record with storage link
    const { data: updatedMaterial, error: updateError } = await supabase
      .from('student_materials')
      .update({ storage_bucket_link: storagePath })
      .eq('id', material.id)
      .select()
      .single()

    if (updateError) throw new Error(updateError.message)

    return {
      data: updatedMaterial as StudentMaterial,
      error: null,
    }
  } catch (error) {
    return {
      data: null,
      error: error as Error,
    }
  }
}

/**
 * Downloads a file from the storage bucket
 */
export async function downloadStudentMaterial(
  storagePath: string
): Promise<{ data: Blob | null; error: Error | null }> {
  const { data, error } = await supabase.storage
    .from(STUDENT_MATERIALS_BUCKET)
    .download(storagePath)

  return {
    data,
    error: error ? new Error(error.message) : null,
  }
}

/**
 * Gets a public URL for a file in the storage bucket
 */
export function getStudentMaterialUrl(storagePath: string): string {
  const { data } = supabase.storage.from(STUDENT_MATERIALS_BUCKET).getPublicUrl(storagePath)
  return data.publicUrl
}

/**
 * Gets all student materials
 */
export async function getAllStudentMaterials(): Promise<{
  data: StudentMaterial[] | null
  error: Error | null
}> {
  const { data, error } = await supabase
    .from('student_materials')
    .select()
    .order('created_at', { ascending: false })

  return {
    data: data as StudentMaterial[] | null,
    error: error ? new Error(error.message) : null,
  }
}

/**
 * Gets student materials by type
 */
export async function getStudentMaterialsByType(
  type: MaterialType
): Promise<{ data: StudentMaterial[] | null; error: Error | null }> {
  const { data, error } = await supabase
    .from('student_materials')
    .select()
    .eq('type', type)
    .order('created_at', { ascending: false })

  return {
    data: data as StudentMaterial[] | null,
    error: error ? new Error(error.message) : null,
  }
}

/**
 * Gets a single student material by ID
 */
export async function getStudentMaterial(
  id: string
): Promise<{ data: StudentMaterial | null; error: Error | null }> {
  const { data, error } = await supabase.from('student_materials').select().eq('id', id).single()

  return {
    data: data as StudentMaterial | null,
    error: error ? new Error(error.message) : null,
  }
}

/**
 * Updates a student material record
 */
export async function updateStudentMaterial(
  id: string,
  updates: UpdateStudentMaterial
): Promise<{ data: StudentMaterial | null; error: Error | null }> {
  const { data, error } = await supabase
    .from('student_materials')
    .update(updates)
    .eq('id', id)
    .select()
    .single()

  return {
    data: data as StudentMaterial | null,
    error: error ? new Error(error.message) : null,
  }
}

/**
 * Deletes a student material record and its associated file
 */
export async function deleteStudentMaterial(
  id: string
): Promise<{ error: Error | null }> {
  try {
    // Get the material to find storage path
    const { data: material, error: fetchError } = await getStudentMaterial(id)
    if (fetchError || !material) throw fetchError || new Error('Material not found')

    // Delete file from storage if it exists
    if (material.storage_bucket_link) {
      const { error: storageError } = await supabase.storage
        .from(STUDENT_MATERIALS_BUCKET)
        .remove([material.storage_bucket_link])

      if (storageError) throw new Error(storageError.message)
    }

    // Delete the material record
    const { error: deleteError } = await supabase
      .from('student_materials')
      .delete()
      .eq('id', id)

    if (deleteError) throw new Error(deleteError.message)

    return { error: null }
  } catch (error) {
    return { error: error as Error }
  }
}
