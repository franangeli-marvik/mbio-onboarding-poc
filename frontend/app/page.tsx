import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-blue-50/30 to-emerald-50/40 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full text-center space-y-12">
        <div className="space-y-4">
          <h1 className="text-6xl font-serif font-semibold text-gray-900">
            M.bio
          </h1>
          <p className="text-xl text-gray-600 max-w-lg mx-auto">
            Create your AI-powered professional profile in minutes
          </p>
        </div>

        <div className="flex flex-col gap-4 max-w-md mx-auto">
          <Link
            href="/profile/new"
            className="px-8 py-4 bg-msu-green text-white rounded-full text-lg font-medium hover:bg-msu-green-light transition-colors shadow-lg hover:shadow-xl"
          >
            Create Your Profile
          </Link>

          <Link
            href="/demo"
            className="px-8 py-4 bg-white text-gray-700 rounded-full text-lg font-medium hover:shadow-lg transition-all border-2 border-gray-200 hover:border-msu-green-light"
          >
            View Demo Profile
          </Link>
        </div>

      </div>
    </div>
  );
}
