import "./globals.css"
import type { Metadata } from "next"
import { Archivo_Black, IBM_Plex_Sans } from "next/font/google"

const archivoBlack = Archivo_Black({
  subsets: ["latin"],
  variable: "--font-newsreader",
  weight: "400",
})

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-spline",
  weight: ["300", "400", "500", "600"],
})

export const metadata: Metadata = {
  title: "arXlearn",
  description: "PhD level learning in half the time. LLM-augmented learning plans that translate new topics into your native expertise.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${archivoBlack.variable} ${ibmPlexSans.variable} antialiased`}>
        {children}
      </body>
    </html>
  )
}
