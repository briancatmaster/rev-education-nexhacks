import "./globals.css"
import type { Metadata } from "next"
import { Newsreader, Spline_Sans } from "next/font/google"

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
})

const splineSans = Spline_Sans({
  subsets: ["latin"],
  variable: "--font-spline",
})

export const metadata: Metadata = {
  title: "NexHacks Learning",
  description: "LLM-augmented learning plans that translate new topics into your native expertise.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${newsreader.variable} ${splineSans.variable} antialiased`}>
        {children}
      </body>
    </html>
  )
}
